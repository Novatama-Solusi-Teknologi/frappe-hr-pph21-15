import frappe
import re
from frappe.model.document import Document
from frappe.utils import cint, getdate

from frappe_hr_pph21.tax.engine import dec, profile_values
from frappe_hr_pph21.tax.rules import SUPPORTED_YEARS
from frappe_hr_pph21.queries import employee_values


class PPh21EmployeeTaxProfile(Document):
    def before_validate(self):
        if self.employee:
            values = employee_values(self.employee)
            self.company = values['company']
            self.employee_name = values['employee_name']
            self.ptkp_status = self.ptkp_status or values['ptkp_status']

    def autoname(self):
        self.name = f"{self.employee}-{self.tax_year}"

    def validate(self):
        self.tax_year = cint(self.tax_year)
        if self.tax_year not in SUPPORTED_YEARS:
            frappe.throw("Tahun pajak didukung: 2024–2026.")
        employee = frappe.get_doc("Employee", self.employee)
        if employee.company != self.company:
            frappe.throw("Company harus sama dengan perusahaan pegawai.")
        self.ter_category = profile_values(self.ptkp_status)[0]
        if not self.tax_identity_validated:
            frappe.throw("Validasi NIK/NPWP pegawai untuk tarif normal sebelum mengaktifkan profil. Tarif tanpa identitas valid belum didukung.")
        identity = re.sub(r"[ .-]", "", self.tax_id or "")
        if not re.fullmatch(r"[0-9]{15,16}", identity):
            frappe.throw("Isi NIK/NPWP 15 atau 16 digit yang valid.")
        if not self.permanent_employee or not self.resident_full_year or self.facility != "Normal":
            frappe.throw("Rilis ini hanya untuk pegawai tetap, WP dalam negeri sepanjang tahun, tanpa fasilitas DTP.")
        cutoff = cint(self.opening_through_month)
        if not 0 <= cutoff <= 11:
            frappe.throw("Saldo awal sampai bulan harus 0–11.")
        for field in ("opening_gross", "opening_allowance", "opening_deductions", "opening_tax"):
            if dec(self.get(field)) < 0:
                frappe.throw("Saldo awal tidak boleh negatif.")
            if not cutoff and dec(self.get(field)):
                frappe.throw("Isi bulan saldo awal bila nominal saldo awal diisi.")
        if dec(self.opening_tax) != dec(self.opening_tax).to_integral_value():
            frappe.throw("PPh saldo awal harus dalam rupiah penuh.")
        if dec(self.opening_allowance) > dec(self.opening_gross):
            frappe.throw("Tunjangan pajak saldo awal sudah termasuk dan tidak boleh melebihi bruto saldo awal.")
        if cutoff and not self.opening_reference:
            frappe.throw("Isi referensi kertas kerja saldo awal.")
        join = getdate(employee.date_of_joining)
        if join.year > self.tax_year or (cutoff and join.year == self.tax_year and cutoff < join.month):
            frappe.throw("Tahun/bulan saldo awal tidak sesuai tanggal mulai bekerja.")
        if employee.relieving_date:
            leave = getdate(employee.relieving_date)
            if leave.year < self.tax_year or (cutoff and leave.year == self.tax_year and cutoff >= leave.month):
                frappe.throw("Saldo awal tidak boleh meliputi masa pajak terakhir pegawai.")
        duplicate = frappe.db.exists("PPh21 Employee Tax Profile", {
            "employee": self.employee, "tax_year": self.tax_year, "name": ["!=", self.name or ""],
        })
        if duplicate:
            frappe.throw("Profil pegawai untuk tahun ini sudah ada.")
        old = self.get_doc_before_save()
        if old and frappe.db.exists("Salary Slip", {"pph21_tax_profile": self.name, "docstatus": 1}):
            fields = ("employee", "company", "tax_year", "ptkp_status", "method", "tax_id", "tax_identity_validated",
                      "resident_full_year", "permanent_employee", "facility", "opening_through_month",
                      "opening_gross", "opening_allowance", "opening_deductions", "opening_tax")
            if any(old.get(field) != self.get(field) for field in fields):
                frappe.throw("Profil sudah digunakan pada slip submitted. Batalkan slip terkait sebelum koreksi profil/saldo awal.")
