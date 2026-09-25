import frappe
from frappe.utils import getdate

from frappe_hr_pph21.setup import component_role, component_has_submitted_slips


def validate_salary_structure(doc, method=None):
    for row in list(doc.get("earnings") or []) + list(doc.get("deductions") or []):
        if component_role(row.salary_component):
            frappe.throw("Komponen PPh21 Potongan Pajak ditambahkan otomatis ke Salary Slip. Hapus dari Salary Structure.")


def validate_additional_salary(doc, method=None):
    if component_role(doc.salary_component):
        frappe.throw("Komponen PPh21 Potongan Pajak tidak boleh dimasukkan melalui Additional Salary.")
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
    if not component_role(doc.name) and not frappe.db.exists("PPh21 Component Tax Mapping", {
        "salary_component": doc.name, "noncash_offset_component": ["is", "set"],
    }):
        return
    companies = [r.company for r in doc.accounts]
    if len(companies) != len(set(companies)):
        frappe.throw("Salary Component: hanya satu baris Accounts per Company; Payroll Entry membaca satu akun.")
    old = doc.get_doc_before_save()
    if not old:
        return
    frappe.db.sql('SELECT name FROM `tabSalary Component` WHERE name=%s FOR UPDATE', (doc.name,))
    fields = ('type', 'salary_component_abbr', 'is_tax_applicable', 'depends_on_payment_days',
              'variable_based_on_taxable_salary', 'statistical_component', 'do_not_include_in_total',
              'is_flexible_benefit', 'amount_based_on_formula', 'only_tax_impact',
              'do_not_include_in_accounts', 'formula', 'condition', 'disabled')
    old_accounts = {r.company: r.account for r in old.accounts}
    new_accounts = {r.company: r.account for r in doc.accounts}
    for company in old_accounts.keys() | new_accounts.keys():
        # Filling a missing legacy mapping is allowed; changing an existing posted mapping is not.
        changed_account = old_accounts.get(company) and old_accounts.get(company) != new_accounts.get(company)
        if (changed_account or any(old.get(f) != doc.get(f) for f in fields)) and component_has_submitted_slips(doc.name, company):
            frappe.throw('Komponen PPh21 sudah digunakan pada slip submitted; akun dan atribut perhitungannya dikunci.')
