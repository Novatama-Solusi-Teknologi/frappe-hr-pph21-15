import frappe
from frappe.utils import getdate

from frappe_hr_pph21.setup import component_role, component_has_submitted_slips, is_noncash_offset, is_tax_component, validate_noncash_account


def validate_salary_structure(doc, method=None):
    for row in list(doc.get("earnings") or []) + list(doc.get("deductions") or []):
        if component_role(row.salary_component) or is_tax_component(row.salary_component) or is_noncash_offset(row.salary_component):
            frappe.throw("Komponen hasil pajak diisi oleh app. Hapus komponen pajak atau pasangan noncash lama dari Salary Structure.")


def validate_additional_salary(doc, method=None):
    if component_role(doc.salary_component) or is_tax_component(doc.salary_component) or is_noncash_offset(doc.salary_component):
        frappe.throw("Komponen pajak/pasangan noncash tidak boleh dimasukkan melalui Additional Salary.")
    if not doc.employee or not frappe.db.get_value("Employee", doc.employee, "pph21_enabled"):
        return
    # Prevent bonuses being added after the month's canonical slip is posted.
    if doc.get("is_recurring"):
        start, end = getdate(doc.from_date), getdate(doc.to_date)
    elif doc.get("payroll_date"):
        start = end = getdate(doc.payroll_date)
    else:
        return
    if frappe.db.exists("Salary Slip", {
        "employee": doc.employee, "company": doc.company, "docstatus": 1,
        "start_date": ["<=", end], "end_date": [">=", start], "pph21_tax_profile": ["is", "set"],
    }):
        frappe.throw("Masa pajak sudah memiliki slip submitted. Batalkan/amend slip sebelum menambah penghasilan masa tersebut.")


def validate_generated_component(doc, method=None):
    old = doc.get_doc_before_save()
    old_rows = old.accounts or [] if old else []
    direct = any(r.get("pph21_noncash_payable_account") for r in list(doc.accounts or []) + list(old_rows))
    if not direct and not component_role(doc.name) and not is_tax_component(doc.name) and not is_noncash_offset(doc.name) and not frappe.db.exists("PPh21 Component Tax Mapping", {
        "salary_component": doc.name, "noncash_offset_component": ["is", "set"],
    }):
        return
    companies = [r.company for r in doc.accounts]
    if len(companies) != len(set(companies)):
        frappe.throw("Salary Component: hanya satu baris Accounts per Company; Payroll Entry membaca satu akun.")
    for row in doc.accounts:
        if row.get("pph21_noncash_payable_account"):
            if doc.type != "Earning" or not doc.do_not_include_in_total or doc.statistical_component:
                frappe.throw("Akun Utang Noncash hanya untuk Earning noncash, Do Not Include in Total dicentang, bukan Statistical Component.")
            validate_noncash_account(row.account, row.company, "Expense")
            validate_noncash_account(row.pph21_noncash_payable_account, row.company, "Liability")
    if not old:
        return
    frappe.db.sql('SELECT name FROM `tabSalary Component` WHERE name=%s FOR UPDATE', (doc.name,))
    fields = ('type', 'salary_component_abbr', 'is_tax_applicable', 'depends_on_payment_days',
              'variable_based_on_taxable_salary', 'statistical_component', 'do_not_include_in_total',
              'is_flexible_benefit', 'amount_based_on_formula', 'only_tax_impact',
              'do_not_include_in_accounts', 'formula', 'condition', 'amount', 'disabled')
    old_accounts = {r.company: r.account for r in old.accounts}
    new_accounts = {r.company: r.account for r in doc.accounts}
    old_payables = {r.company: r.get("pph21_noncash_payable_account") for r in old.accounts}
    new_payables = {r.company: r.get("pph21_noncash_payable_account") for r in doc.accounts}
    for company in old_accounts.keys() | new_accounts.keys():
        # Filling a missing legacy mapping is allowed; changing an existing posted mapping is not.
        changed_account = old_accounts.get(company) and old_accounts.get(company) != new_accounts.get(company)
        changed_payable = old_payables.get(company) and old_payables.get(company) != new_payables.get(company)
        if (changed_account or changed_payable or any(old.get(f) != doc.get(f) for f in fields)) and component_has_submitted_slips(doc.name, company):
            frappe.throw('Komponen PPh21 sudah digunakan pada slip submitted; akun dan atribut perhitungannya dikunci.')
