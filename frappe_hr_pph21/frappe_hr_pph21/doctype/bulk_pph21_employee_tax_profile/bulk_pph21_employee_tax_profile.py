"""Batch profile setup: draft has no effect; submit applies all rows atomically."""
import re

import frappe
from frappe.model.document import Document
from frappe.utils import cint

from frappe_hr_pph21.queries import employee_values
from frappe_hr_pph21.tax.rules import PTKP, SUPPORTED_YEARS
from frappe_hr_pph21.fiscal_year import tax_year_from_fiscal_year

PROFILE = 'PPh21 Employee Tax Profile'


class BulkPPh21EmployeeTaxProfile(Document):
    def before_validate(self):
        self.default_tax_year = tax_year_from_fiscal_year(self.default_fiscal_year)
        self.default_method = self.default_method or 'Gross Up'
        for row in self.employees:
            if not row.fiscal_year and row.tax_year and cint(row.tax_year) != self.default_tax_year:
                frappe.throw(f'Baris {row.idx}: pilih Fiscal Year sesuai tahun profil lama.')
            row.fiscal_year = row.fiscal_year or self.default_fiscal_year
            row.method = row.method or self.default_method
            if row.employee:
                values = employee_values(row.employee)
                row.company = values['company']
                row.employee_name = values['employee_name']
                row.ptkp_status = row.ptkp_status or values['ptkp_status']
            row.tax_year = tax_year_from_fiscal_year(row.fiscal_year, row.company)
            row.tax_id = (row.tax_id or '').strip()

    def validate(self):
        if not 1 <= len(self.employees) <= 200:
            frappe.throw('Isi 1 sampai 200 baris profil per batch.')
        if self.default_tax_year not in SUPPORTED_YEARS or self.default_method not in ('Gross', 'Gross Up'):
            frappe.throw('Periksa tahun pajak default (2024-2026) dan metode default.')
        self.employee_count = len(self.employees)
        seen = set()
        for row in self.employees:
            key = (row.employee, cint(row.tax_year))
            if not row.employee or key in seen:
                frappe.throw(f'Baris {row.idx}: karyawan kosong atau duplikat karyawan/tahun pajak.')
            seen.add(key)
            if key[1] not in SUPPORTED_YEARS:
                frappe.throw(f'Baris {row.idx}: tahun pajak didukung 2024-2026.')
            if row.ptkp_status not in PTKP:
                frappe.throw(f'Baris {row.idx}: pilih PTKP yang valid; custom_ptkp kosong/tidak dikenali perlu diisi manual.')
            if row.method not in ('Gross', 'Gross Up'):
                frappe.throw(f'Baris {row.idx}: pilih Gross atau Gross Up.')
            if row.tax_id and not re.fullmatch(r'[0-9]{15,16}', re.sub(r'[ .-]', '', row.tax_id)):
                frappe.throw(f'Baris {row.idx}: NIK/NPWP harus 15 atau 16 digit.')
            # Draft result columns are not accepted as evidence that a profile was processed.
            if self.docstatus == 0:
                row.tax_profile = None
                row.result = None

    def before_submit(self):
        self.check_permission('submit')
        if cint(self.confirm_standard_assumptions) != 1:
            frappe.throw('Konfirmasikan persyaratan standar seluruh baris sebelum Submit.')
        # All affected employee locks use the same ordering, including batches with multiple companies.
        # Existing profiles also get a row lock below, matching payroll's profile lock.
        frappe.db.savepoint('pph21_bulk_profiles')
        try:
            for name in sorted({row.employee for row in self.employees}):
                employee = frappe.get_doc('Employee', name, for_update=True)
                employee.check_permission('read')
            for row in self.employees:
                self.apply_row(row)
        except Exception:
            frappe.db.rollback(save_point='pph21_bulk_profiles')
            raise

    def apply_row(self, row):
        # Refresh Company after acquiring locks; never trust a client-supplied company.
        values = employee_values(row.employee)
        row.company = values['company']
        row.employee_name = values['employee_name']
        existing = frappe.db.exists(PROFILE, {'employee': row.employee, 'tax_year': row.tax_year})
        fields = dict(employee=row.employee, company=row.company, tax_year=row.tax_year,
                      fiscal_year=row.fiscal_year, ptkp_status=row.ptkp_status, method=row.method)
        if row.tax_id:
            fields['tax_id'] = row.tax_id
        if existing:
            profile = frappe.get_doc(PROFILE, existing, for_update=True)
            profile.check_permission('read')
            profile.check_permission('write')
            if row.tax_id and row.tax_id != profile.tax_id:
                fields['tax_identity_validated'] = 0
            if any(profile.get(key) != value for key, value in fields.items()):
                # Normal validation protects profiles referenced by submitted Salary Slips.
                # Opening balances and all fields outside the five bulk inputs remain unchanged.
                profile.update(fields)
                profile.save()
                row.result = 'Diperbarui'
            else:
                row.result = 'Tidak berubah'
        else:
            profile = frappe.new_doc(PROFILE)
            profile.update(fields)
            profile.update(dict(tax_identity_validated=0, resident_full_year=1,
                                permanent_employee=1, facility='Normal', opening_through_month=0,
                                opening_gross=0, opening_allowance=0, opening_deductions=0, opening_tax=0))
            profile.insert()
            row.result = 'Dibuat'
        row.tax_profile = profile.name

    def before_cancel(self):
        frappe.throw('Batch yang sudah diterapkan tidak dapat dibatalkan. Koreksi melalui profil individual atau batch baru sesuai proteksi payroll.')
