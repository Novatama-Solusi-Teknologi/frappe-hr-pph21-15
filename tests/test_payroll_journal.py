"""Native HRMS v15 journal/bank arithmetic with mocked query results and accounts.
No database persistence or live Journal Entry validation is simulated here.
"""
import ast
from pathlib import Path
import types
import unittest

import test_v15_adapter as adapter

SOURCE = Path(__file__).resolve().parents[2] / '.build/contract_source/payroll_entry.py'


def journal_contract(slip, env, employee_wise=False):
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
    rows = [adapter.Box(r, parentfield=table, employee=slip.employee, salary_structure=slip.salary_structure)
            for table in ('earnings', 'deductions') for r in slip[table]]
    # Query boundary: native get_salary_components/get_salary_slip_details both
    # select these flags. The arithmetic below is compiled from actual HRMS.
    selected = [r for r in rows if not r.do_not_include_in_total or not r.do_not_include_in_accounts]
    def get_value(dt, name, field, **kwargs):
        if dt == 'Salary Component Account':
            component = name['parent']
            assert field == 'account'
            if component == 'Basic': return 'Salary Expense'
            if component == 'BPJS': return 'Expense BPJS'
            if component == 'Employee BPJS': return 'Liability BPJS'
            return env.component(component).accounts[0].account
        if dt == 'Salary Component':
            # Components in these cases are non-statistical and not flexible benefits.
            return tuple(0 for _ in field) if isinstance(field, (list, tuple)) else 0
        raise AssertionError(dt)
    frappe = types.SimpleNamespace(db=types.SimpleNamespace(get_value=get_value,
        get_single_value=lambda *a: int(employee_wise)), get_cached_value=get_value,
        get_precision=lambda *a: 2)
    ns = {'frappe': frappe, 'flt': adapter.flt, 'cint': lambda v: int(v or 0), '_': lambda s: s,
          'erpnext': types.SimpleNamespace(get_company_currency=lambda c: 'IDR'),
          'get_accounting_dimensions': lambda: []}
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(SOURCE), 'exec'), ns)
    payroll_cls = type('NativePayroll', (adapter.Box,), {n: ns[n] for n in names})
    payroll = payroll_cls(company='PT PUP', name='PAYROLL', doctype='Payroll Entry',
                          payroll_payable_account='Salary Payable', cost_center='Main',
                          start_date=slip.start_date, end_date=slip.end_date)
    payroll.check_permission = lambda p: None
    payroll.get_salary_components = lambda kind: [r for r in selected if r.parentfield == kind]
    payroll.get_salary_slip_details = lambda withheld: selected
    payroll.get_advance_deduction = lambda *a: None
    payroll.get_payroll_cost_centers_for_employee = lambda *a: {'Main': 60, 'Factory': 40}
    payroll.get_amount_and_exchange_rate_for_journal_entry = lambda account, amount, *a: (1, amount)
    payroll.update_accounting_dimensions = lambda *a: None
    journal = []
    payroll.make_journal_entry = lambda accounts, *a, **k: journal.extend(accounts)
    payroll.make_accrual_jv_entry([slip.name])
    accrual_employee = dict(payroll.employee_based_payroll_payable_entries)
    bank = []
    payroll.process_loan_repayments_for_bank_entry = lambda rows: 0
    payroll.set_accounting_entries_for_bank_entry = lambda amount, *a: bank.append(amount)
    payroll.make_bank_entry()
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
