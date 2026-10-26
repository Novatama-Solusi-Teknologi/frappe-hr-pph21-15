"""Native HRMS v15 journal/bank arithmetic with mocked query results and accounts.
No database persistence or live Journal Entry validation is simulated here.
"""
import ast
import copy
import json
import importlib.util
import sys
from unittest.mock import patch
from pathlib import Path
import types
import unittest

import test_v15_adapter as adapter

SOURCE = Path(__file__).resolve().parents[2] / '.build/contract_source/payroll_entry.py'


def journal_contract(slip, env, employee_wise=False, extra_slips=(), repeat=False, withheld=False):
    tree = ast.parse(SOURCE.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'PayrollEntry')
    names = {'get_salary_component_account', 'get_account', 'get_salary_component_total',
             'should_add_component_to_accrual_jv', 'make_accrual_jv_entry',
             'get_payable_amount_for_earnings_and_deductions', 'get_accounting_entries_and_payable_amount',
             'set_payable_amount_against_payroll_payable_account', 'set_employee_based_payroll_payable_entries',
             'set_accounting_entries_for_advance_deductions', 'make_bank_entry'}
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(methods) == len(names)
    for method in methods:
        method.decorator_list = []
    slips=[slip,*extra_slips]
    for doc in slips: doc.docstatus=1;doc.payroll_entry='PAYROLL'
    rows = [adapter.Box(r, name=doc.name, parentfield=table, employee=doc.employee, salary_structure=doc.salary_structure)
            for doc in slips for table in ('earnings', 'deductions') for r in doc[table]]
    # Query boundary: native get_salary_components/get_salary_slip_details both
    # select these flags. The arithmetic below is compiled from actual HRMS.
    selected = [r for r in rows if not r.do_not_include_in_total or not r.do_not_include_in_accounts]
    def get_value(dt, name, field, **kwargs):
        if dt == 'Salary Component Account':
            component = name['parent']
            assert field == 'account'
            if component == 'Basic': return 'Salary Expense'
            if component in ('BPJS','BPJS Pension'): return 'Expense BPJS'
            if component == 'Employee BPJS': return 'Liability BPJS'
            return env.component(component).accounts[0].account
        if dt == 'Salary Component':
            # Components in these cases are non-statistical and not flexible benefits.
            return tuple(0 for _ in field) if isinstance(field, (list, tuple)) else 0
        raise AssertionError(dt)
    frappe = types.SimpleNamespace(db=types.SimpleNamespace(get_value=get_value,
        get_single_value=lambda *a: int(employee_wise)), get_cached_value=get_value,
        get_precision=lambda *a: 2, _dict=adapter.Box, throw=adapter.fail,
        get_doc=lambda dt,name,**kw: next(d for d in slips if d.name==name) if dt=="Salary Slip" else env.frappe.get_doc(dt,name,**kw))
    ns = {'frappe': frappe, 'flt': adapter.flt, 'cint': lambda v: int(v or 0), '_': lambda s: s,
          'erpnext': types.SimpleNamespace(get_company_currency=lambda c: 'IDR'),
          'get_accounting_dimensions': lambda: []}
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(SOURCE), 'exec'), ns)
    payroll_cls = type('NativePayroll', (adapter.Box,), {n: ns[n] for n in names})
    payroll_cls.get_salary_components=lambda self,kind: [r for r in selected if r.parentfield==kind and not next(d for d in slips if d.name==r.name).get('journal_entry')]
    payroll_cls.get_salary_slip_details=lambda self,for_withheld_salaries=False: [r for r in selected if (next(d for d in slips if d.name==r.name).get("status")=="Withheld")==for_withheld_salaries]
    module=types.ModuleType('hrms.payroll.doctype.payroll_entry.payroll_entry');module.PayrollEntry=payroll_cls
    spec=importlib.util.spec_from_file_location('payroll_override_test',SOURCE.parents[2]/'frappe-hr-pph21/frappe_hr_pph21/overrides/payroll_entry.py')
    with patch.dict(sys.modules,{'frappe':frappe,'frappe.utils':env.utils,'frappe_hr_pph21.setup':env.setup,
        'hrms.payroll.doctype.payroll_entry.payroll_entry':module}):
        override=importlib.util.module_from_spec(spec);spec.loader.exec_module(override)
    payroll = override.PPh21PayrollEntry(company='PT PUP', name='PAYROLL', doctype='Payroll Entry',
                          payroll_payable_account='Salary Payable', cost_center='Main',
                          start_date=slip.start_date, end_date=slip.end_date)
    payroll.check_permission = lambda p: None
    payroll.get_sal_slip_list=lambda **kw: [adapter.Box(name=d.name) for d in slips if not d.get('journal_entry')]
    payroll.get_advance_deduction = lambda *a: None
    payroll.get_payroll_cost_centers_for_employee = lambda *a: {'Main': 60, 'Factory': 40}
    payroll.get_amount_and_exchange_rate_for_journal_entry = lambda account, amount, *a: (1, amount)
    payroll.update_accounting_dimensions = lambda *a: None
    journal = []
    def post(accounts,*a,**k):
        journal.extend(accounts)
        for doc in slips: doc.journal_entry='JV'
    payroll.make_journal_entry=post
    payroll.make_accrual_jv_entry([d.name for d in slips])
    accrual_employee = dict(payroll.employee_based_payroll_payable_entries)
    if repeat:
        before=list(journal);payroll.make_accrual_jv_entry([d.name for d in slips])
        assert journal==before, "Retry created another journal"
    bank = []
    payroll.process_loan_repayments_for_bank_entry = lambda rows: 0
    payroll.set_accounting_entries_for_bank_entry = lambda amount, *a: (bank.append(amount) or adapter.Box(name="BANK"))
    # HRMS withheld linking service is a boundary double.
    ns['link_bank_entry_in_salary_withholdings']=lambda *a: None
    payroll.make_bank_entry(for_withheld_salaries=withheld)
    return journal, bank, accrual_employee, payroll.employee_based_payroll_payable_entries


@unittest.skipUnless(SOURCE.exists() and adapter.SOURCE, 'Requires pinned HRMS v15 source files')
class PayrollJournalTest(unittest.TestCase):
    def fixture(self, method='Gross Up', treatment='Taxable Noncash'):
        case = adapter.V15AdapterTest(); case.setUp()
        case.env.profile.method = method
        case.env.settings.component_mapping += [case.noncash_mapping(treatment=treatment),
            adapter.Box(salary_component='Employee BPJS', treatment='Ignore')]
        case.slip.templates['earnings'].append(adapter.row('BPJS', 480000, 0))
        case.slip.templates['deductions'].append(adapter.row('Employee BPJS', 120000, 0))
        return case

    def assert_journal(self, case, employee_wise=False):
        slip = case.calc()
        journal, bank, accrual_employee, bank_employee = journal_contract(slip, case.env, employee_wise)
        totals = {}
        for line in journal:
            totals[line['account']] = totals.get(line['account'], 0) + line.get('debit_in_account_currency', 0) - line.get('credit_in_account_currency', 0)
        self.assertAlmostEqual(sum(totals.values()), 0, places=2)
        self.assertEqual(totals['Expense BPJS'], 480000)
        self.assertEqual(totals['Liability BPJS'], -600000)  # company 480k + employee 120k
        self.assertEqual(totals['Salary Payable'], -slip.net_pay)
        self.assertEqual(bank, [slip.net_pay])
        self.assertEqual(totals.get('Tax Expense', 0), slip.pph21_tax_allowance)
        self.assertEqual(totals.get('Tax Payable', 0), slip.pph21_tax_refund - slip.pph21_tax_withholding)
        self.assertTrue(all(not r.do_not_include_in_accounts for r in slip.earnings + slip.deductions))
        self.assertEqual(len([r for r in journal if r['account']=='Expense BPJS']), 2)  # cost centers
        if employee_wise:
            for entries in (accrual_employee, bank_employee):
                e = entries[slip.employee]
                self.assertEqual(e['earnings'] - e['deductions'], slip.net_pay)
        return slip

    def test_gross_up_bpjs_and_pph21_are_in_the_same_balanced_accrual(self):
        for employee_wise in (False, True):
            with self.subTest(employee_wise=employee_wise):
                slip = self.assert_journal(self.fixture(), employee_wise)
                self.assertEqual(slip.net_pay, 9880000)

    def test_gross_withholding_and_nontaxable_employer_bpjs(self):
        for method, treatment in [('Gross', 'Taxable Noncash'), ('Gross Up', 'Non Taxable')]:
            with self.subTest(method=method, treatment=treatment):
                self.assert_journal(self.fixture(method, treatment))

    def test_two_sources_share_payable_account_without_counterpart_in_journal_and_bank(self):
        case=self.fixture()
        case.slip.templates['earnings'][-1].amount=400000
        case.slip.templates['earnings'][-1].default_amount=400000
        case.env.salary_components['BPJS Pension']=adapter.Box(case.env.salary_components['BPJS'],name='BPJS Pension')
        case.env.settings.component_mapping.append(case.noncash_mapping('BPJS Pension','Non Taxable'))
        case.slip.templates['earnings'].append(adapter.row('BPJS Pension',80000,0))
        self.assert_journal(case,True)
        pairs=[r for r in case.slip.deductions if r.salary_component=='Utang BPJS Perusahaan']
        self.assertEqual(pairs,[])

    def test_shared_manual_tax_names_work_across_settings_structures_and_methods(self):
        for method,setting,structure in [('Gross Up','Office','Office Salary'),('Gross','Factory','Factory Salary')]:
            with self.subTest(method=method):
                case=self.fixture(method)
                case.select_manual_tax_components()
                case.env.settings.name=setting;case.env.profile.pph21_settings=setting
                case.slip.salary_structure=structure
                slip=self.assert_journal(case,True)
                self.assertEqual([r.salary_component for r in slip.deductions if r.salary_component=='PPh21'],['PPh21'])
                self.assertFalse(any('PPH21-SET' in r.salary_component for r in slip.earnings+slip.deductions))
        case=self.fixture();case.select_manual_tax_components()
        case.env.employee.relieving_date=adapter.date(2026,2,25)
        case.set_period('2026-01-26','2026-02-25','2026-02-25')
        case.env.profile.update(opening_through_month=1,opening_gross=10230179,opening_tax=230179)
        slip=self.assert_journal(case,True)
        self.assertEqual([r.amount for r in slip.earnings if r.salary_component=='Refund PPh21'],[230179])

    def test_mixed_new_legacy_and_native_slips_post_once_and_bank_pays_cash(self):
        case=self.fixture();direct=case.calc()
        legacy=copy.deepcopy(direct);legacy.name='LEGACY';legacy.employee='EMP-OLD'
        snap=json.loads(legacy.pph21_tax_snapshot);snap.pop('noncash_accounting_mode');snap['app_version']='0.9.0'
        legacy.pph21_tax_snapshot=json.dumps(snap)
        legacy.deductions.append(adapter.Box(adapter.row('Utang BPJS Perusahaan',480000,0),do_not_include_in_total=1))
        native=adapter.Box(name='NATIVE',employee='EMP-NATIVE',company='PT PUP',salary_structure='Native',
            earnings=[adapter.row('Basic',1000000,0)],deductions=[],pph21_tax_snapshot=None)
        journal,bank,_,_=journal_contract(direct,case.env,True,[legacy,native],repeat=True)
        total={}
        for r in journal: total[r['account']]=total.get(r['account'],0)+r.get('debit_in_account_currency',0)-r.get('credit_in_account_currency',0)
        self.assertAlmostEqual(sum(total.values()),0)
        self.assertEqual(total['Expense BPJS'],960000)
        self.assertEqual(total['Liability BPJS'],-1200000)
        self.assertEqual(bank,[direct.net_pay+legacy.net_pay+1000000])

    def test_accrual_uses_saved_accounts_even_if_source_master_changes(self):
        case=self.fixture();slip=case.calc()
        case.env.salary_components['BPJS'].accounts[0].pph21_noncash_payable_account='Liability Changed'
        journal,bank,_,_=journal_contract(slip,case.env)
        self.assertNotIn('Liability Changed',[r['account'] for r in journal])
        self.assertIn('Liability BPJS',[r['account'] for r in journal])
        self.assertEqual(bank,[slip.net_pay])

    def test_damaged_snapshot_or_detail_mismatch_blocks_accrual(self):
        for change in ('amount','account','duplicate','json','mode'):
            with self.subTest(change=change):
                case=self.fixture();slip=case.calc();snap=json.loads(slip.pph21_tax_snapshot)
                if change=='amount': snap['noncash_accounting'][0]['amount']='1'
                if change=='account': snap['noncash_accounting'][0]['payable_account']=''
                if change=='duplicate': snap['noncash_accounting']*=2
                if change=='mode': snap.pop('noncash_accounting_mode')
                slip.pph21_tax_snapshot='{' if change=='json' else json.dumps(snap)
                with self.assertRaisesRegex(ValueError,'snapshot jurnal noncash'):
                    journal_contract(slip,case.env)

    def test_withheld_bank_payment_excludes_noncash_source(self):
        case=self.fixture();slip=case.calc();slip.status='Withheld'
        _,bank,_,_=journal_contract(slip,case.env,True,withheld=True)
        self.assertEqual(bank,[slip.net_pay])

    def test_final_refund_debits_tax_payable_without_losing_bpjs_liability(self):
        case = self.fixture()
        case.env.employee.relieving_date = adapter.date(2026, 2, 25)
        case.set_period('2026-01-26', '2026-02-25', '2026-02-25')
        case.env.profile.update(opening_through_month=1, opening_gross=10230179, opening_tax=230179)
        slip = self.assert_journal(case, True)
        self.assertEqual(slip.pph21_tax_refund, 230179)
        self.assertEqual(slip.net_pay, 10110179)


if __name__ == '__main__':
    unittest.main()
