import frappe
from frappe.utils import getdate

from frappe_hr_pph21.setup import COMPONENTS


def validate_salary_structure(doc, method=None):
    for row in list(doc.get("earnings") or []) + list(doc.get("deductions") or []):
        if row.salary_component in COMPONENTS:
            frappe.throw("Komponen PPh21 Potongan Pajak ditambahkan otomatis ke Salary Slip. Hapus dari Salary Structure.")


def validate_additional_salary(doc, method=None):
    if doc.salary_component in COMPONENTS:
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
    from calendar import monthrange
    start = start.replace(day=1)
    end = end.replace(day=monthrange(end.year, end.month)[1])
    if frappe.db.exists("Salary Slip", {
        "employee": doc.employee, "company": doc.company, "docstatus": 1,
        "start_date": ["between", [start, end]], "pph21_tax_profile": ["is", "set"],
    }):
        frappe.throw("Masa pajak sudah memiliki slip submitted. Batalkan/amend slip sebelum menambah penghasilan masa tersebut.")
