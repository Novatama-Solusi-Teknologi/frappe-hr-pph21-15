"""Post direct noncash expense/liability in the native Payroll Entry journal.

The native journal lifecycle, dimensions, references, submit/cancel and bank entry
remain in HRMS. Old snapshots with actual counterpart rows use the native path.
"""
import json

import frappe
from frappe.utils import flt
from hrms.payroll.doctype.payroll_entry.payroll_entry import PayrollEntry

from frappe_hr_pph21.setup import validate_noncash_account
from frappe_hr_pph21.tax.engine import dec


def direct_ledger(slip):
    raw = slip.get("pph21_tax_snapshot")
    if not raw:
        if slip.get("pph21_tax_profile"):
            frappe.throw(f"Salary Slip {slip.name}: snapshot jurnal noncash/PPh21 tidak tersedia; periksa slip sebelum posting.")
        return []
    try:
        snapshot = json.loads(raw)
        mode = snapshot.get("noncash_accounting_mode")
        if mode != "direct_accounts":
            version = str(snapshot.get("app_version") or "0.0").split(".")[:2]
            if mode or (all(v.isdigit() for v in version) and tuple(map(int, version)) >= (0, 10)):
                raise ValueError("missing or unsupported routing mode")
            return []  # Legacy slip retains its real counterpart Salary Detail.
        entries = snapshot.get("noncash_accounting", [])
        expected, actual = {}, {}
        for entry in entries:
            name, amount = entry["component"], dec(entry["amount"])
            if name in expected or not amount.is_finite() or amount < 0:
                raise ValueError("duplicate/invalid amount")
            if not entry.get("expense_account") or not entry.get("payable_account"):
                raise ValueError("missing account")
            expected[name] = amount
        for row in slip.earnings:
            if row.do_not_include_in_total:
                if row.do_not_include_in_accounts:
                    raise ValueError("noncash excluded from accounting")
                actual[row.salary_component] = actual.get(row.salary_component, dec(0)) + dec(row.amount)
        if actual != expected:
            raise ValueError("snapshot differs from salary details")
        return entries
    except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
        frappe.throw(f"Salary Slip {slip.name}: snapshot jurnal noncash tidak cocok dengan baris slip. Periksa dan koreksi slip melalui alur cancel/amend; jurnal tidak dibuat.")


class PPh21PayrollEntry(PayrollEntry):
    def make_accrual_jv_entry(self, submitted_salary_slips):
        self.check_permission("write")
        slips, routes = [], []
        for record in self.get_sal_slip_list(ss_status=1, as_dict=True):
            slip = frappe.get_doc("Salary Slip", record.name, for_update=True)
            if slip.company != self.company or slip.docstatus != 1 or slip.payroll_entry != self.name:
                frappe.throw("Salary Slip jurnal harus submitted pada Company dan Payroll Entry yang sama.")
            for entry in direct_ledger(slip):
                validate_noncash_account(entry["expense_account"], self.company, "Expense", for_update=True)
                validate_noncash_account(entry["payable_account"], self.company, "Liability", for_update=True)
                routes.append(dict(entry, slip=slip.name, employee=slip.employee,
                                   salary_structure=slip.salary_structure))
            slips.append(slip)
        self._pph21_journal_slips = slips if routes else None
        self._pph21_journal_routes = routes
        try:
            return super().make_accrual_jv_entry(submitted_salary_slips)
        finally:
            self._pph21_journal_slips = None
            self._pph21_journal_routes = []

    def get_salary_components(self, component_type):
        slips = getattr(self, "_pph21_journal_slips", None)
        if slips is None:
            return super().get_salary_components(component_type)
        direct = {(r["slip"], r["component"]) for r in self._pph21_journal_routes}
        rows = []
        for slip in slips:
            for row in slip.get(component_type) or []:
                if (slip.name, row.salary_component) in direct:
                    continue
                # Same eligibility rule as HRMS v15, scoped by the native slip list.
                if row.do_not_include_in_total and row.do_not_include_in_accounts:
                    continue
                rows.append(frappe._dict(salary_component=row.salary_component, amount=row.amount,
                    parentfield=component_type, additional_salary=row.additional_salary,
                    salary_structure=slip.salary_structure, employee=slip.employee))
        return rows

    def get_salary_component_total(self, component_type=None, employee_wise_accounting_enabled=False):
        totals = super().get_salary_component_total(component_type, employee_wise_accounting_enabled) or {}
        for entry in getattr(self, "_pph21_journal_routes", None) or []:
            account = entry["expense_account"] if component_type == "earnings" else entry["payable_account"]
            cost_centers = self.get_payroll_cost_centers_for_employee(entry["employee"], entry["salary_structure"])
            for cost_center, percentage in cost_centers.items():
                amount = flt(entry["amount"]) * percentage / 100
                key = (account, cost_center)
                totals[key] = totals.get(key, 0) + amount
                if employee_wise_accounting_enabled:
                    # Equal debit/credit contributions cancel in the employee payable.
                    self.set_employee_based_payroll_payable_entries(component_type, entry["employee"], amount)
        return totals

    def get_salary_slip_details(self, for_withheld_salaries=False):
        rows = super().get_salary_slip_details(for_withheld_salaries)
        direct_by_slip = {}
        for row in rows:
            if row.name not in direct_by_slip:
                slip = frappe.get_doc("Salary Slip", row.name)
                direct_by_slip[row.name] = {entry["component"] for entry in direct_ledger(slip)}
        # Bank Entry pays only cash salary. Legacy source/counterpart rows still cancel normally.
        return [row for row in rows if row.salary_component not in direct_by_slip[row.name]]
