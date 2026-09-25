"""Controller contract tests: actual v15 arithmetic methods, mocked DB/services.
Not a substitute for bench installation/SQL/GL integration tests.
"""
import ast
from datetime import date
from decimal import Decimal
import importlib.util
import json
from hashlib import sha256
import os
import sqlite3
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
    def append(self, table, values=None):
        row = Box(values or {})
        self.setdefault(table, []).append(row)
        return row

def getdate(value): return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])
def flt(value, precision=None): return round(float(value or 0), precision) if precision is not None else float(value or 0)
def fail(message): raise ValueError(message)

class Environment:
    def __init__(self):
        self.employee = Box(company='PT PUP', date_of_joining=date(2026,1,1), relieving_date=None, pph21_enabled=1)
        self.profile = Box(name='EMP-001-2026', pph21_settings='PUP Standard', ptkp_status='TK/0', ter_category='A', method='Gross Up', permanent_employee=1, resident_full_year=1, facility='Normal', opening_through_month=0, opening_gross=0, opening_allowance=0, opening_deductions=0, opening_tax=0, opening_reference='')
        self.profile.tax_identity_validated = 1
        self.settings = Box(name='PUP Standard', settings_name='PUP Standard', allowance_component=ALLOWANCE, withholding_component=TAX, refund_component=REFUND, enabled=1, company='PT PUP', rounding='Floor IDR', expense_account='Tax Expense', tax_payable_account='Tax Payable', component_mapping=[Box(salary_component='Basic', treatment='Taxable Cash')])
        self.tax_accounts={ALLOWANCE:'Tax Expense',TAX:'Tax Payable',REFUND:'Tax Payable'}
        self.structure, self.history = Box(earnings=[], deductions=[]), []
        self.salary_components = {
            'BPJS': Box(name='BPJS',accounts=[Box(company='PT PUP',account='Expense BPJS')],type='Earning',statistical_component=0,do_not_include_in_total=1,do_not_include_in_accounts=1),
            'Basic': Box(type='Earning',statistical_component=0,do_not_include_in_total=0,do_not_include_in_accounts=0),
        }
        self.locked, self.newer = False, False
        self.frappe = types.ModuleType('frappe')
        self.frappe.db = Box(get_value=self.get_value, exists=lambda *a: self.newer, sql=self.sql)
        self.frappe.throw = fail
        self.frappe.get_doc = lambda dt, name, **kw: self.salary_components.get(name,Box(name=name,type='Earning',do_not_include_in_total=0)) if dt=='Salary Component' else Box(name=name,company='PT PUP',root_type='Expense' if 'Expense' in name else 'Liability',is_group=0,disabled=0,account_currency='IDR') if dt=='Account' else {'Employee':self.employee, 'PPh21 Settings':self.settings, 'PPh21 Employee Tax Profile':self.profile, 'Salary Structure':self.structure}[dt]
        self.frappe.get_all = lambda *a, **k: self.history
        self.utils = types.ModuleType('frappe.utils')
        self.utils.getdate, self.utils.flt, self.utils.cint = getdate, flt, lambda x: int(x or 0)
        self.setup = types.ModuleType('frappe_hr_pph21.setup')
        self.setup.ALLOWANCE, self.setup.WITHHOLDING, self.setup.REFUND, self.setup.COMPONENTS = ALLOWANCE,TAX,REFUND,COMPONENTS
        self.setup.validate_component = self.component
        self.setup.component_role = lambda name: 'PPh21 Utang Noncash' if str(name).startswith('PPh21 Utang Noncash [') else next((b for b in COMPONENTS if name == b or str(name).startswith(b+' [')),None)
        self.setup.settings_components = lambda settings: {ALLOWANCE:settings.allowance_component,TAX:settings.withholding_component,REFUND:settings.refund_component}
        helper_names={'noncash_component_name','component_account','validate_noncash_account'}
        tree=ast.parse((ROOT/'frappe_hr_pph21/setup.py').read_text())
        ns={'frappe':self.frappe,'sha256':sha256,'NONCASH_OFFSET':'PPh21 Utang Noncash'}
        exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in helper_names],type_ignores=[]),'setup.py','exec'),ns)
        for key in helper_names: setattr(self.setup,key,ns[key])
    def get_value(self, dt, filters, field, **kw):
        if dt=='Employee': return self.employee.get(field)
        if dt=='Company': return 'IDR'
        if dt=='PPh21 Settings': return 'PT PUP'
        if dt=='PPh21 Employee Tax Profile': return self.profile.name if self.profile else None
        if dt=='Salary Component': return 0
        raise AssertionError(dt)
    def sql(self, query, params, **kwargs):
        self.locked = self.locked or 'FOR UPDATE' in query
        if 'pph21_tax_month>' in query:
            return [('NEWER',)] if self.newer else []
        if 'tabSalary Slip' in query:
            return self.history
        return [(params[0],)]
    def component(self,name,**kwargs):
        if name in self.salary_components: return self.salary_components[name]
        base = self.setup.component_role(name)
        if base=='PPh21 Utang Noncash':
            return Box(name=name,type='Deduction',salary_component_abbr='NC',accounts=[Box(company='PT PUP',account='Liability BPJS')])
        kind,abbr,taxable = COMPONENTS[base]
        return Box(name=name,type=kind,salary_component_abbr=abbr,is_tax_applicable=taxable,accounts=[Box(company='PT PUP',account=self.tax_accounts[base])])

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
    names = {'calculate_net_pay','set_net_pay','get_component_totals','set_precision_for_component_amounts','get_amount_based_on_payment_days','update_component_row','update_component_amount_based_on_payment_days'}
    methods = [n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert len(methods)==len(names)
    ns = dict(frappe=env.frappe,flt=flt,cint=lambda x:int(x or 0),rounded=round,getdate=getdate,set_loan_repayment=lambda self:None,get_period_factor=lambda *a,**k:(1,12))
    exec(compile(ast.Module(body=methods,type_ignores=[]),SOURCE,'exec'),ns)
    salary = types.ModuleType('hrms.payroll.doctype.salary_slip.salary_slip')
    salary.SalarySlip = type('V15Base',(Base,),{n:ns[n] for n in names})
    spec = importlib.util.spec_from_file_location('pph21_adapter_contract',ROOT/'frappe_hr_pph21/overrides/salary_slip.py')
    with patch.dict(sys.modules,{'frappe':env.frappe,'frappe.utils':env.utils,'frappe_hr_pph21.setup':env.setup,'hrms.payroll.doctype.salary_slip.salary_slip':salary}):
        helper_spec=importlib.util.spec_from_file_location('settings_adapter_test',ROOT/'frappe_hr_pph21/settings.py')
        helper=importlib.util.module_from_spec(helper_spec);helper_spec.loader.exec_module(helper)
        with patch.dict(sys.modules, {'frappe_hr_pph21.settings':helper}):
            mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod.PPh21SalarySlip

def row(name='Basic',amount=10000000,depends=1):
    return Box(salary_component=name,abbr=name.upper(),amount=amount,default_amount=amount,additional_amount=0,additional_salary=None,depends_on_payment_days=depends,variable_based_on_taxable_salary=0,do_not_include_in_total=0,do_not_include_in_accounts=0)

@unittest.skipUnless(SOURCE and Path(SOURCE).is_file(),'Set HRMS_SALARY_SLIP_SOURCE for controller contract tests')
class V15AdapterTest(unittest.TestCase):
    def setUp(self):
        self.env=Environment();cls=load_controller(self.env)
        self.slip=cls(employee='EMP-001',company='PT PUP',name='JAN',posting_date=date(2026,1,31),start_date=date(2026,1,1),end_date=date(2026,1,31),currency='IDR',exchange_rate=1,payroll_frequency='Monthly',salary_slip_based_on_timesheet=0,salary_structure='Test',earnings=[],deductions=[],total_working_days=30,payment_days=30,payroll_period=None,total_loan_repayment=0,hour_rate=0,_salary_structure_doc=Box(salary_component=None),joining_date=date(2026,1,1),relieving_date=None,templates={'earnings':[row()],'deductions':[]})
    def noncash_mapping(self, name='BPJS', treatment='Taxable Noncash'):
        return Box(salary_component=name,treatment=treatment,noncash_payable_account='Liability BPJS',
                   noncash_offset_component=self.env.setup.noncash_component_name(self.env.settings.name,name))
    def calc(self): self.slip.calculate_net_pay();return self.slip
    def test_repeated_calculation_and_native_tax_suppression(self):
        s=self.calc(); snapshot=s.pph21_tax_snapshot
        self.assertEqual((s.gross_pay,s.total_deduction,s.net_pay),(10230179,230179,10000000))
        self.assertFalse(s.native_tax_called); self.assertFalse(s.native_breakup_called)
        self.calc(); self.assertEqual(s.pph21_tax_snapshot,snapshot)
        self.assertEqual([r.salary_component for r in s.earnings].count(ALLOWANCE),1)
    def test_settings_selected_by_profile_and_recorded_in_snapshot(self):
        original_get_doc=self.env.frappe.get_doc
        seen=[]
        def get_doc(dt,name,**kwargs):
            if dt=='PPh21 Settings': seen.append(name)
            return original_get_doc(dt,name,**kwargs)
        self.env.frappe.get_doc=get_doc
        self.env.profile.pph21_settings='PUP Production'
        self.env.settings.name='PUP Production'
        self.env.settings.settings_name='PUP - Produksi'
        self.env.tax_accounts[ALLOWANCE]='Production Expense'
        self.env.tax_accounts[TAX]='Production Liability'
        self.env.tax_accounts[REFUND]='Refund Liability'
        self.env.settings.allowance_component=ALLOWANCE+' [PUP Production]'
        self.env.settings.withholding_component=TAX+' [PUP Production]'
        self.env.settings.refund_component=REFUND+' [PUP Production]'
        s=self.calc();snapshot=json.loads(s.pph21_tax_snapshot)
        self.assertEqual(seen,['PUP Production'])
        self.assertEqual(snapshot['settings'],'PUP Production')
        self.assertEqual(snapshot['accounts'],{'allowance':'Production Expense','tax':'Production Liability','refund':'Refund Liability'})
        self.assertEqual(s.pph21_tax_settings,'PUP Production')
        self.assertEqual(s.earnings[-1].salary_component,self.env.settings.allowance_component)
        self.assertEqual(s.deductions[-1].salary_component,self.env.settings.withholding_component)
        self.calc();self.assertEqual(len(s.earnings),2)
        self.assertEqual(s.net_pay,10000000)

    def test_accounts_are_read_only_from_components_not_obsolete_settings(self):
        self.env.settings.expense_account='Obsolete'
        self.env.settings.tax_payable_account='Obsolete'
        s=self.calc()
        self.assertEqual(json.loads(s.pph21_tax_snapshot)['accounts'],
            dict(allowance='Tax Expense',tax='Tax Payable',refund='Tax Payable'))
        self.env.salary_components[ALLOWANCE]=Box(name=ALLOWANCE,accounts=[])
        with self.assertRaisesRegex(ValueError,'tepat satu akun'): self.calc()

    def test_profile_without_settings_or_wrong_company_cannot_run_payroll(self):
        self.env.profile.pph21_settings=None
        with self.assertRaisesRegex(ValueError,'Pilih PPh21 Settings'): self.calc()
        self.env.profile.pph21_settings='Other'
        self.env.settings.company='Other Company'
        with self.assertRaisesRegex(ValueError,'Company'): self.calc()

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
        self.env.settings.component_mapping.append(self.noncash_mapping())
        r=row('BPJS',400000,0);r.do_not_include_in_total=r.do_not_include_in_accounts=1
        self.slip.templates['earnings'].append(r);s=self.calc()
        self.assertEqual(s.pph21_tax_base,10400000);self.assertEqual(s.net_pay,10000000)
    def test_noncash_master_flags_override_stale_structure_flags_before_native_totals(self):
        self.env.settings.component_mapping.append(self.noncash_mapping())
        # Actual HRMS v15 row creation copies these stale flags from the structure.
        stale=row('BPJS',480000,0)
        self.slip.update_component_row(stale,480000,'earnings')
        self.assertEqual(self.slip.earnings[0].do_not_include_in_accounts,0)
        self.slip.templates['earnings'].append(Box(self.slip.earnings[0]))
        s=self.calc()
        self.assertEqual(s.pph21_tax_base,10480000)
        self.assertEqual(s.net_pay,10000000)
        noncash=next(r for r in s.earnings if r.salary_component=='BPJS')
        self.assertEqual((noncash.do_not_include_in_total,noncash.do_not_include_in_accounts),(1,0))
        self.assertEqual(s.gross_pay,10000000+s.pph21_tax_allowance)
        self.assertEqual(stale.do_not_include_in_total,0)  # no write to the structure/master
        snapshot=s.pph21_tax_snapshot
        self.calc();self.assertEqual(s.pph21_tax_snapshot,snapshot)
        s.before_submit();self.assertEqual(s.net_pay,10000000)

    def test_noncash_excluded_from_first_native_total_and_master_locked_on_submit(self):
        self.env.settings.component_mapping.append(self.noncash_mapping())
        self.slip.templates['earnings'].append(row('BPJS',480000,0))
        parent=type(self.slip).__bases__[0]
        native_totals=parent.get_component_totals
        totals=[]
        reads=[]
        get_doc=self.env.frappe.get_doc
        def recorded_get_doc(dt,name,**kwargs):
            if dt=='Salary Component' and name=='BPJS': reads.append(kwargs.get('for_update'))
            return get_doc(dt,name,**kwargs)
        def recorded_total(doc,component_type,depends_on_payment_days=0):
            total=native_totals(doc,component_type,depends_on_payment_days)
            if component_type=='earnings': totals.append(total)
            return total
        self.env.frappe.get_doc=recorded_get_doc
        with patch.object(parent,'get_component_totals',recorded_total):
            self.calc()
            self.assertEqual(totals[0],10000000)
            self.assertEqual(reads,[False])
            self.slip.before_submit()
            self.assertEqual(reads,[False,True])

    def test_noncash_statistical_structure_row_is_rejected_before_it_disappears(self):
        self.env.settings.component_mapping.append(self.noncash_mapping())
        r=row('BPJS',480000,0);r.statistical_component=1
        self.env.structure.earnings=[r]
        with self.assertRaisesRegex(ValueError,'Statistical Component pada baris Salary Structure'): self.calc()

    def test_noncash_master_must_be_correct_even_if_slip_flags_are_checked(self):
        self.env.settings.component_mapping.append(self.noncash_mapping())
        r=row('BPJS',480000,0);r.do_not_include_in_total=r.do_not_include_in_accounts=1
        self.slip.templates['earnings'].append(r)
        for field in ('do_not_include_in_total',):
            with self.subTest(field=field):
                self.env.salary_components['BPJS'][field]=0
                with self.assertRaisesRegex(ValueError,'Salary Component BPJS'): self.calc()
                self.env.salary_components['BPJS'][field]=1

    def test_noncash_master_is_reread_on_submit(self):
        self.env.settings.component_mapping.append(self.noncash_mapping())
        r=row('BPJS',480000,0);r.do_not_include_in_total=r.do_not_include_in_accounts=1
        self.slip.templates['earnings'].append(r)
        self.calc()
        self.env.salary_components['BPJS'].do_not_include_in_total=0
        with self.assertRaisesRegex(ValueError,'Salary Component BPJS'): self.slip.before_submit()

    def test_noncash_additional_salary_and_gross_method_keep_noncash_out_of_net(self):
        self.env.profile.method='Gross'
        self.env.settings.component_mapping.append(self.noncash_mapping())
        r=row('BPJS',480000,0);r.additional_salary='ADDITIONAL-TEST'
        self.slip.templates['earnings'].append(r)
        s=self.calc()
        self.assertEqual(s.gross_pay,10000000)
        self.assertEqual(s.net_pay,10000000-float(monthly(10480000,'TK/0','Gross').withholding))
        data=json.loads(s.pph21_tax_snapshot)
        detail=next(d for d in data['components'] if d['component']=='BPJS')
        self.assertEqual(detail['additional_salary'],'ADDITIONAL-TEST')
        self.assertEqual(detail['do_not_include_in_accounts'],0)

    def test_noncash_offsets_match_actual_prorata_and_multiple_additional_rows(self):
        mapping=self.noncash_mapping();self.env.settings.component_mapping.append(mapping)
        self.slip.payment_days=15
        self.slip.templates['earnings'] += [row('BPJS',400000,1),row('BPJS',100000,0)]
        self.slip.templates['earnings'][-1].additional_salary='EXTRA'
        s=self.calc();pairs=[r for r in s.deductions if r.salary_component==mapping.noncash_offset_component]
        self.assertEqual(len(pairs),1);self.assertEqual(pairs[0].amount,300000)
        self.assertEqual((pairs[0].do_not_include_in_total,pairs[0].do_not_include_in_accounts),(1,0))
        self.assertEqual(s.net_pay,5000000)
        self.assertEqual(s.pph21_tax_base,5300000)
        self.assertEqual(json.loads(s.pph21_tax_snapshot)['noncash_accounting'][0]['amount'],'300000.0')
        self.calc();self.assertEqual(len([r for r in s.deductions if r.salary_component==mapping.noncash_offset_component]),1)

    def test_non_taxable_noncash_is_journalled_without_increasing_tax_or_net_pay(self):
        self.env.settings.component_mapping.append(self.noncash_mapping(treatment='Non Taxable'))
        self.slip.templates['earnings'].append(row('BPJS',480000,0))
        s=self.calc()
        self.assertEqual((s.pph21_tax_base,s.net_pay),(10000000,10000000))
        self.assertEqual(json.loads(s.pph21_tax_snapshot)['noncash_accounting'][0]['payable_account'],'Liability BPJS')

    def test_missing_noncash_account_and_wrong_pair_cannot_silently_use_salary_payable(self):
        self.env.settings.component_mapping.append(Box(salary_component='BPJS',treatment='Taxable Noncash'))
        self.slip.templates['earnings'].append(row('BPJS',480000,0))
        with self.assertRaisesRegex(ValueError,'komponen pasangan noncash'): self.calc()
        self.env.settings.component_mapping[-1]=self.noncash_mapping()
        name=self.env.settings.component_mapping[-1].noncash_offset_component
        self.env.salary_components[name]=Box(name=name,accounts=[])
        with self.assertRaisesRegex(ValueError,'tepat satu akun'): self.calc()

    def test_separate_benefit_accounting_and_unmapped_noncash_cannot_bypass_journal(self):
        self.env.salary_components['Basic'].only_tax_impact=1
        with self.assertRaisesRegex(ValueError,'Only Tax Impact'): self.calc()
        self.env.salary_components['Basic'].only_tax_impact=0
        self.env.settings.component_mapping.append(Box(salary_component='BPJS',treatment='Non Taxable'))
        self.slip.templates['earnings'].append(row('BPJS',480000,0))
        with self.assertRaisesRegex(ValueError,'simpan mapping Settings'): self.calc()

    def test_unmapped_component_rejected(self):
        self.env.settings.component_mapping=[]
        with self.assertRaisesRegex(ValueError,'Petakan'): self.calc()
    def test_noncash_configuration_rejected(self):
        self.env.settings.component_mapping[0].treatment='Taxable Noncash'
        with self.assertRaisesRegex(ValueError,'noncash harus'): self.calc()
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
        with self.assertRaisesRegex(ValueError,'maksimum 31 hari'): self.calc()
        self.slip.end_date=date(2025,12,31)
        with self.assertRaisesRegex(ValueError,'berurutan'): self.calc()
        self.slip.end_date=date(2026,1,31);self.slip.currency='USD'
        with self.assertRaisesRegex(ValueError,'IDR'): self.calc()
    def test_official_annual_example_via_migration(self):
        self.slip.start_date,self.slip.end_date=date(2026,12,1),date(2026,12,31)
        self.slip.posting_date=date(2026,12,31)
        self.env.profile.update(opening_through_month=11,opening_gross=110000000,opening_tax=2200000,opening_deductions=1100000,ptkp_status='K/0',method='Gross')
        self.env.settings.component_mapping.append(Box(salary_component='Pension',treatment='Annual Deduction'))
        self.slip.templates['deductions']=[row('Pension',100000,0)];s=self.calc()
        self.assertEqual((s.pph21_tax_final,s.pph21_tax_annual,s.pph21_tax_withholding,s.net_pay),(1,2715000,515000,9385000))
    def test_resignation_refund(self):
        self.env.employee.relieving_date=date(2026,2,28)
        self.slip.posting_date=date(2026,2,28)
        self.slip.start_date,self.slip.end_date=date(2026,2,1),date(2026,2,28)
        self.env.profile.update(opening_through_month=1,opening_gross=10230179,opening_tax=230179,opening_allowance=230179)
        s=self.calc();self.assertEqual((s.pph21_tax_refund,s.pph21_tax_allowance,s.net_pay),(230179,0,10230179))
        self.assertIn(REFUND,[r.salary_component for r in s.earnings])
    def test_missing_history_and_duplicate_month(self):
        self.slip.posting_date=date(2026,2,28)
        self.slip.start_date,self.slip.end_date=date(2026,2,1),date(2026,2,28)
        with self.assertRaisesRegex(ValueError,'belum lengkap'): self.calc()
        self.env.history=[Box(name='OTHER',start_date=date(2026,1,1),end_date=date(2026,1,31),posting_date=date(2026,2,1))]
        with self.assertRaisesRegex(ValueError,'masa yang sama/lebih baru'): self.calc()
    def test_submitted_history_accumulates(self):
        self.env.history=[Box(self.calc())]
        self.slip.posting_date=date(2026,2,28)
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
    def test_optional_identity_does_not_block_payroll(self):
        self.env.profile.tax_identity_validated=0
        self.env.profile.tax_id = ''
        slip = self.calc()
        self.assertEqual(slip.pph21_tax_withholding, 230179)

    def set_period(self, start, end, paid, name='CUT-OFF'):
        self.slip.update(start_date=getdate(start), end_date=getdate(end), posting_date=getdate(paid), name=name)

    def test_pup_cutoff_26_to_25_uses_payment_month_and_preserves_prorata(self):
        self.set_period('2026-08-26', '2026-09-25', '2026-09-25')
        self.env.profile.update(opening_through_month=8, opening_gross=80000000, opening_tax=1600000)
        self.slip.total_working_days=31
        self.slip.payment_days=25
        s=self.calc()
        self.assertEqual((s.pph21_tax_year,s.pph21_tax_month,s.pph21_tax_final),(2026,9,0))
        self.assertEqual(s.pph21_tax_base,round(10000000*25/31,2))
        self.assertEqual((s.start_date,s.end_date),(date(2026,8,26),date(2026,9,25)))
        data=json.loads(s.pph21_tax_snapshot)
        self.assertEqual((data['payment_date'],data['payroll_start_date'],data['payroll_end_date']),
                         ('2026-09-25','2026-08-26','2026-09-25'))
        self.assertEqual(data['prior_gross'],'80000000')
        s.before_submit()
        self.assertEqual(s.pph21_tax_month,9)
        self.assertTrue(self.env.locked)

    def test_payment_date_required_and_drives_profile_lookup(self):
        self.slip.posting_date=None
        with self.assertRaisesRegex(ValueError,'Posting Date'): self.calc()
        self.set_period('2025-12-26','2026-01-25','2026-01-25')
        self.env.employee.date_of_joining=date(2020,1,1)
        orig=self.env.get_value
        def checked(dt, filters, field, **kwargs):
            if dt=='PPh21 Employee Tax Profile': self.assertEqual(filters['tax_year'],2026)
            return orig(dt,filters,field,**kwargs)
        self.env.frappe.db.get_value=checked
        self.assertEqual((self.calc().pph21_tax_year,self.slip.pph21_tax_month,self.slip.pph21_tax_final),(2026,1,0))

    def test_history_uses_stored_payment_month_across_cutoffs(self):
        self.set_period('2025-12-26','2026-01-25','2026-01-25','JAN')
        self.env.employee.date_of_joining=date(2020,1,1)
        self.env.history=[Box(self.calc())]
        self.set_period('2026-01-26','2026-02-25','2026-02-25','FEB')
        data=json.loads(self.calc().pph21_tax_snapshot)
        self.assertEqual(data['prior_slips'],['JAN'])
        self.assertEqual(data['prior_tax'],'230179.0')
        self.slip.before_submit()
        self.assertEqual(json.loads(self.slip.pph21_tax_snapshot)['prior_slips'],['JAN'])

    def test_payment_month_can_differ_from_both_work_period_months(self):
        self.set_period('2026-08-26','2026-09-25','2026-10-01')
        self.env.profile.update(opening_through_month=9, opening_gross=90000000, opening_tax=1800000)
        self.assertEqual(self.calc().pph21_tax_month,10)
        self.assertEqual(self.slip.pph21_tax_payment_date,date(2026,10,1))

    def test_history_sql_selection_preserves_scope_and_legacy_periods(self):
        # Execute the selection itself, not a canned list: company/docstatus,
        # stored tax year, posting year and overlapping dates all matter.
        self.env.employee.date_of_joining=date(2020,1,1)
        old=Box(self.calc())
        old.posting_date=date(2025,12,31)  # legacy stored January 2026 still wins
        records=[old]
        for name, changes in [('OTHER-COMPANY',{'company':'Other'}),
                              ('OTHER-EMPLOYEE',{'employee':'Other'}),
                              ('CANCELLED',{'docstatus':2})]:
            clone=Box(old);clone.update(name=name,**changes);records.append(clone)
        fields=['name','employee','company','docstatus','start_date','end_date','posting_date',
                'pph21_tax_year','pph21_tax_month','pph21_tax_profile','pph21_tax_gross','pph21_tax_allowance',
                'pph21_tax_deductions','pph21_tax_withholding','pph21_tax_refund','pph21_tax_final','pph21_tax_snapshot']
        db=sqlite3.connect(':memory:');self.addCleanup(db.close);db.row_factory=sqlite3.Row
        db.execute('CREATE TABLE `tabSalary Slip` ('+', '.join(fields)+')')
        for record in records:
            record.setdefault('docstatus',1)
            values=[str(record[f]) if isinstance(record.get(f),date) else record.get(f) for f in fields]
            db.execute('INSERT INTO `tabSalary Slip` VALUES ('+','.join('?' for f in fields)+')',values)
        original=self.env.sql
        def sql(query,params,**kwargs):
            if 'FROM `tabSalary Slip`' not in query: return original(query,params,**kwargs)
            params=[str(v) if isinstance(v,date) else v for v in params]
            return [Box(r) for r in db.execute(query.replace(' FOR UPDATE','').replace('%s','?'),params)]
        self.env.frappe.db.sql=sql
        self.set_period('2026-02-01','2026-02-28','2026-02-28','FEB')
        self.assertEqual(json.loads(self.calc().pph21_tax_snapshot)['prior_slips'],['JAN'])
        self.slip.before_submit()
        self.assertEqual(json.loads(self.slip.pph21_tax_snapshot)['prior_slips'],['JAN'])

    def test_duplicate_payment_month_rejected_even_distinct_work_periods(self):
        self.set_period('2026-01-01','2026-01-15','2026-01-15','FIRST')
        self.env.history=[Box(self.calc())]
        self.set_period('2026-01-16','2026-01-31','2026-01-31','SECOND')
        with self.assertRaisesRegex(ValueError,'masa yang sama/lebih baru'): self.calc()

    def test_overlap_rejected_even_when_payment_year_changes(self):
        self.set_period('2025-12-01','2025-12-31','2026-01-01')
        self.env.employee.date_of_joining=date(2020,1,1)
        self.env.history=[Box(name='OLD',start_date=date(2025,12,1),end_date=date(2025,12,31),
            posting_date=date(2025,12,31),pph21_tax_profile='OLD-PROFILE',pph21_tax_year=2025,pph21_tax_month=12)]
        with self.assertRaisesRegex(ValueError,'tumpang tindih'): self.calc()

    def test_cutoff_opening_balances_and_missing_payment_history(self):
        self.set_period('2026-08-26','2026-09-25','2026-09-25')
        with self.assertRaisesRegex(ValueError,'belum lengkap'): self.calc()
        self.env.profile.opening_through_month=9
        with self.assertRaisesRegex(ValueError,'dicakup saldo awal'): self.calc()
        self.env.profile.opening_through_month=8
        self.assertEqual(self.calc().pph21_tax_month,9)

    def test_december_cutoff_reconciles_in_payment_year(self):
        self.set_period('2026-11-26','2026-12-25','2026-12-25')
        self.env.profile.update(opening_through_month=11,opening_gross=110000000,opening_tax=2200000,
                                opening_deductions=1100000,ptkp_status='K/0',method='Gross')
        self.env.settings.component_mapping.append(Box(salary_component='Pension',treatment='Annual Deduction'))
        self.slip.templates['deductions']=[row('Pension',100000,0)]
        s=self.calc()
        self.assertEqual((s.pph21_tax_month,s.pph21_tax_final,s.pph21_tax_annual,s.pph21_tax_withholding),(12,1,2715000,515000))

    def test_new_joiner_after_cutoff_does_not_require_unpaid_join_month(self):
        self.env.employee.date_of_joining=date(2026,8,28)
        self.set_period('2026-08-26','2026-09-25','2026-09-25','SEP')
        self.env.history=[Box(self.calc())]
        self.set_period('2026-09-26','2026-10-25','2026-10-25','OCT')
        data=json.loads(self.calc().pph21_tax_snapshot)
        self.assertEqual(data['first_payment_month'],9)
        self.assertEqual(data['prior_slips'],['SEP'])

    def test_legacy_stored_tax_month_not_relabelled_by_posting_date(self):
        old=Box(self.calc())
        old.posting_date=date(2026,2,1)
        self.env.history=[old]
        self.set_period('2026-02-01','2026-02-28','2026-02-28','FEB')
        self.assertEqual(json.loads(self.calc().pph21_tax_snapshot)['prior_slips'],['JAN'])

    def test_resignation_cutoff_must_include_last_working_day(self):
        self.env.employee.relieving_date=date(2026,9,28)
        self.env.profile.opening_through_month=8
        self.set_period('2026-09-01','2026-09-25','2026-09-25')
        with self.assertRaisesRegex(ValueError,'sampai tanggal resign'): self.calc()
        self.slip.end_date=date(2026,9,28)
        self.assertEqual(self.calc().pph21_tax_final,1)
        self.slip.posting_date=date(2026,10,1)
        with self.assertRaisesRegex(ValueError,'setelah bulan resign'): self.calc()

    def test_unsupported_payment_year_and_payment_before_period(self):
        self.set_period('2026-12-26','2027-01-25','2027-01-25')
        with self.assertRaises(ValueError): self.calc()
        self.set_period('2026-01-01','2026-01-31','2025-12-31')
        with self.assertRaisesRegex(ValueError,'sebelum Start Date'): self.calc()

if __name__=='__main__': unittest.main()
