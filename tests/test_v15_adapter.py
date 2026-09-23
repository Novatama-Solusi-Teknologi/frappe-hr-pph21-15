"""Controller contract tests: actual v15 arithmetic methods, mocked DB/services.
Not a substitute for bench installation/SQL/GL integration tests.
"""
import ast
from datetime import date
from decimal import Decimal
import importlib.util
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from frappe_hr_pph21.tax.engine import monthly

ROOT = Path(__file__).resolve().parents[1]
SOURCE = os.environ.get('HRMS_SALARY_SLIP_SOURCE', '')
ALLOWANCE, TAX, REFUND = 'PPh21 Tunjangan Pajak', 'PPh21 Potongan Pajak', 'PPh21 Pengembalian Pajak'
COMPONENTS = {ALLOWANCE: ('Earning', 'PPH21_TAX_ALLOW', 1), TAX: ('Deduction', 'PPH21_TAX', 0), REFUND: ('Earning', 'PPH21_TAX_REFUND', 0)}

class Box(dict):
    def __getattr__(self, key): return self.get(key)
    def __setattr__(self, key, value): self[key] = value
    def set(self, key, value): self[key] = value
    def precision(self, key): return 2
    def append(self, table, values):
        row = Box(values)
        self.setdefault(table, []).append(row)
        return row

def getdate(value): return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])
def flt(value, precision=None): return round(float(value or 0), precision) if precision is not None else float(value or 0)
def fail(message): raise ValueError(message)

class Environment:
    def __init__(self):
        self.employee = Box(company='PT PUP', date_of_joining=date(2026,1,1), relieving_date=None, pph21_enabled=1)
        self.profile = Box(name='EMP-001-2026', ptkp_status='TK/0', ter_category='A', method='Gross Up', permanent_employee=1, resident_full_year=1, facility='Normal', opening_through_month=0, opening_gross=0, opening_allowance=0, opening_deductions=0, opening_tax=0, opening_reference='')
        self.profile.tax_identity_validated = 1
        self.settings = Box(enabled=1, company='PT PUP', rounding='Floor IDR', expense_account='Tax Expense', tax_payable_account='Tax Payable', component_mapping=[Box(salary_component='Basic', treatment='Taxable Cash')])
        self.structure, self.history = Box(earnings=[], deductions=[]), []
        self.locked, self.newer = False, False
        self.frappe = types.ModuleType('frappe')
        self.frappe.db = Box(get_value=self.get_value, exists=lambda *a: self.newer, sql=self.sql)
        self.frappe.throw = fail
        self.frappe.get_doc = lambda dt, name, **kw: {'Employee':self.employee, 'PPh21 Settings':self.settings, 'PPh21 Employee Tax Profile':self.profile, 'Salary Structure':self.structure}[dt]
        self.frappe.get_all = lambda *a, **k: self.history
        self.utils = types.ModuleType('frappe.utils')
        self.utils.getdate, self.utils.flt, self.utils.cint = getdate, flt, lambda x: int(x or 0)
        self.setup = types.ModuleType('frappe_hr_pph21.setup')
        self.setup.ALLOWANCE, self.setup.WITHHOLDING, self.setup.REFUND, self.setup.COMPONENTS = ALLOWANCE,TAX,REFUND,COMPONENTS
        self.setup.validate_component = self.component
    def get_value(self, dt, filters, field, **kw):
        if dt=='Employee': return self.employee.get(field)
        if dt=='Company': return 'IDR'
        if dt=='PPh21 Settings': return 'PT PUP'
        if dt=='PPh21 Employee Tax Profile': return self.profile.name if self.profile else None
        if dt=='Salary Component': return 0
        raise AssertionError(dt)
    def sql(self, query, params, **kwargs):
        assert 'FOR UPDATE' in query
        self.locked = True
        if 'pph21_tax_month>' in query:
            return [('NEWER',)] if self.newer else []
        if 'tabSalary Slip' in query:
            return self.history
        return [(params[0],)]
    def component(self,name):
        kind,abbr,taxable = COMPONENTS[name]
        return Box(type=kind,salary_component_abbr=abbr,is_tax_applicable=taxable,accounts=[Box(company='PT PUP',default_account='Tax Expense' if name==ALLOWANCE else 'Tax Payable')])

class Base(Box):
    def calculate_component_amounts(self, table):
        self[table] = [Box(row) for row in self.templates[table]]
        for row in self[table]: row.amount = self.get_amount_based_on_payment_days(row)[0]
        if table=='deductions': self.add_tax_components()
    def add_tax_components(self): self.native_tax_called = True
    def compute_income_tax_breakup(self): self.native_breakup_called = True
    def set_net_total_in_words(self): pass
    def compute_year_to_date(self): self.ytd_called = True
    def compute_month_to_date(self): pass
    def compute_component_wise_year_to_date(self): pass

def load_controller(env):
    tree = ast.parse(Path(SOURCE).read_text())
    cls = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SalarySlip')
    names = {'calculate_net_pay','set_net_pay','get_component_totals','set_precision_for_component_amounts','get_amount_based_on_payment_days'}
    methods = [n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert len(methods)==len(names)
    ns = dict(frappe=env.frappe,flt=flt,cint=lambda x:int(x or 0),rounded=round,getdate=getdate,set_loan_repayment=lambda self:None,get_period_factor=lambda *a,**k:(1,12))
    exec(compile(ast.Module(body=methods,type_ignores=[]),SOURCE,'exec'),ns)
    salary = types.ModuleType('hrms.payroll.doctype.salary_slip.salary_slip')
    salary.SalarySlip = type('V15Base',(Base,),{n:ns[n] for n in names})
    spec = importlib.util.spec_from_file_location('pph21_adapter_contract',ROOT/'frappe_hr_pph21/overrides/salary_slip.py')
    with patch.dict(sys.modules,{'frappe':env.frappe,'frappe.utils':env.utils,'frappe_hr_pph21.setup':env.setup,'hrms.payroll.doctype.salary_slip.salary_slip':salary}):
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod.PPh21SalarySlip

def row(name='Basic',amount=10000000,depends=1):
    return Box(salary_component=name,abbr=name.upper(),amount=amount,default_amount=amount,additional_amount=0,additional_salary=None,depends_on_payment_days=depends,variable_based_on_taxable_salary=0,do_not_include_in_total=0,do_not_include_in_accounts=0)

@unittest.skipUnless(SOURCE and Path(SOURCE).is_file(),'Set HRMS_SALARY_SLIP_SOURCE for controller contract tests')
class V15AdapterTest(unittest.TestCase):
    def setUp(self):
        self.env=Environment();cls=load_controller(self.env)
        self.slip=cls(employee='EMP-001',company='PT PUP',name='JAN',start_date=date(2026,1,1),end_date=date(2026,1,31),currency='IDR',exchange_rate=1,payroll_frequency='Monthly',salary_slip_based_on_timesheet=0,salary_structure='Test',earnings=[],deductions=[],total_working_days=30,payment_days=30,payroll_period=None,total_loan_repayment=0,hour_rate=0,_salary_structure_doc=Box(salary_component=None),joining_date=date(2026,1,1),relieving_date=None,templates={'earnings':[row()],'deductions':[]})
    def calc(self): self.slip.calculate_net_pay();return self.slip
    def test_repeated_calculation_and_native_tax_suppression(self):
        s=self.calc(); snapshot=s.pph21_tax_snapshot
        self.assertEqual((s.gross_pay,s.total_deduction,s.net_pay),(10230179,230179,10000000))
        self.assertFalse(s.native_tax_called); self.assertFalse(s.native_breakup_called)
        self.calc(); self.assertEqual(s.pph21_tax_snapshot,snapshot)
        self.assertEqual([r.salary_component for r in s.earnings].count(ALLOWANCE),1)
    def test_prorata_precedes_tax(self):
        self.slip.payment_days=21;s=self.calc()
        self.assertEqual(s.pph21_tax_base,7000000);self.assertEqual(s.net_pay,7000000)
        self.assertEqual(s.pph21_tax_withholding,monthly(7000000,'TK/0').withholding)
    def test_jht_does_not_reduce_monthly_ter_base(self):
        self.env.settings.component_mapping.append(Box(salary_component='JHT',treatment='Annual Deduction'))
        self.slip.templates['deductions']=[row('JHT',200000,0)];s=self.calc()
        self.assertEqual(s.pph21_tax_withholding,230179);self.assertEqual(s.net_pay,9800000)
        self.assertEqual(s.pph21_tax_deductions,200000)
    def test_noncash_not_paid_to_employee(self):
        self.env.settings.component_mapping.append(Box(salary_component='BPJS',treatment='Taxable Noncash'))
        r=row('BPJS',400000,0);r.do_not_include_in_total=r.do_not_include_in_accounts=1
        self.slip.templates['earnings'].append(r);s=self.calc()
        self.assertEqual(s.pph21_tax_base,10400000);self.assertEqual(s.net_pay,10000000)
    def test_unmapped_component_rejected(self):
        self.env.settings.component_mapping=[]
        with self.assertRaisesRegex(ValueError,'Petakan'): self.calc()
    def test_noncash_configuration_rejected(self):
        self.env.settings.component_mapping[0].treatment='Taxable Noncash'
        with self.assertRaisesRegex(ValueError,'Noncash harus'): self.calc()
    def test_disabled_employee_uses_native(self):
        self.env.employee.pph21_enabled=0;s=self.calc()
        self.assertTrue(s.native_tax_called);self.assertTrue(s.native_breakup_called)
        self.assertFalse(s.pph21_tax_snapshot)
    def test_settings_and_profile_required(self):
        self.env.settings.enabled=0
        with self.assertRaisesRegex(ValueError,'Aktifkan'): self.calc()
        self.env.settings.enabled=1;self.env.profile=None
        with self.assertRaisesRegex(ValueError,'Buat PPh21 Employee Tax Profile'): self.calc()
    def test_unsupported_dtp_and_residency(self):
        self.env.profile.facility='DTP'
        with self.assertRaisesRegex(ValueError,'di luar cakupan'): self.calc()
        self.env.profile.facility='Normal';self.env.profile.resident_full_year=0
        with self.assertRaisesRegex(ValueError,'di luar cakupan'): self.calc()
    def test_calendar_and_currency_guards(self):
        self.slip.end_date=date(2026,2,1)
        with self.assertRaisesRegex(ValueError,'satu bulan'): self.calc()
        self.slip.end_date=date(2026,1,15)
        with self.assertRaisesRegex(ValueError,'seluruh bulan'): self.calc()
        self.slip.end_date=date(2026,1,31);self.slip.currency='USD'
        with self.assertRaisesRegex(ValueError,'IDR'): self.calc()
    def test_official_annual_example_via_migration(self):
        self.slip.start_date,self.slip.end_date=date(2026,12,1),date(2026,12,31)
        self.env.profile.update(opening_through_month=11,opening_gross=110000000,opening_tax=2200000,opening_deductions=1100000,ptkp_status='K/0',method='Gross')
        self.env.settings.component_mapping.append(Box(salary_component='Pension',treatment='Annual Deduction'))
        self.slip.templates['deductions']=[row('Pension',100000,0)];s=self.calc()
        self.assertEqual((s.pph21_tax_final,s.pph21_tax_annual,s.pph21_tax_withholding,s.net_pay),(1,2715000,515000,9385000))
    def test_resignation_refund(self):
        self.env.employee.relieving_date=date(2026,2,28)
        self.slip.start_date,self.slip.end_date=date(2026,2,1),date(2026,2,28)
        self.env.profile.update(opening_through_month=1,opening_gross=10230179,opening_tax=230179,opening_allowance=230179)
        s=self.calc();self.assertEqual((s.pph21_tax_refund,s.pph21_tax_allowance,s.net_pay),(230179,0,10230179))
        self.assertIn(REFUND,[r.salary_component for r in s.earnings])
    def test_missing_history_and_duplicate_month(self):
        self.slip.start_date,self.slip.end_date=date(2026,2,1),date(2026,2,28)
        with self.assertRaisesRegex(ValueError,'belum lengkap'): self.calc()
        self.env.history=[Box(name='OTHER',start_date=date(2026,2,1))]
        with self.assertRaisesRegex(ValueError,'masa yang sama/lebih baru'): self.calc()
    def test_submitted_history_accumulates(self):
        self.env.history=[Box(self.calc())]
        self.slip.start_date,self.slip.end_date=date(2026,2,1),date(2026,2,28);self.slip.name='FEB'
        data=json.loads(self.calc().pph21_tax_snapshot)
        self.assertEqual(Decimal(data['prior_gross']),10230179);self.assertEqual(Decimal(data['prior_tax']),230179)
        self.assertEqual(data['prior_slips'],['JAN'])
    def test_submit_recomputes_under_lock(self):
        s=self.calc();s.pph21_tax_withholding=1;s.deductions[0].amount=1;s.before_submit()
        self.assertTrue(self.env.locked);self.assertEqual(s.total_deduction,230179);self.assertEqual(len(s.pph21_tax_key),64)
    def test_cancel_latest_first(self):
        s=self.calc();s.before_submit();self.env.newer=True
        with self.assertRaisesRegex(ValueError,'masa terbaru'): s.before_cancel()
        self.assertTrue(s.pph21_tax_key);self.env.newer=False;s.before_cancel();self.assertIsNone(s.pph21_tax_key)
    def test_circular_formula_rejected(self):
        r=row();r.formula='PPH21_TAX_ALLOW + 100';self.env.structure.earnings=[r]
        with self.assertRaisesRegex(ValueError,'circular'): self.calc()
    def test_other_tax_component_rejected(self):
        r=row('OtherTax',1000,0);r.variable_based_on_taxable_salary=1;self.env.structure.deductions=[r]
        with self.assertRaisesRegex(ValueError,'pajak standar'): self.calc()
    def test_cannot_disable_midyear_with_posted_history(self):
        self.env.employee.pph21_enabled=0;self.env.newer=True
        with self.assertRaisesRegex(ValueError,'menonaktifkan di tengah tahun'): self.calc()
    def test_unvalidated_tax_identity_rejected(self):
        self.env.profile.tax_identity_validated=0
        with self.assertRaisesRegex(ValueError,'identitas pajak tervalidasi'): self.calc()

if __name__=='__main__': unittest.main()
