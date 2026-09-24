import frappe
from frappe.model.document import Document

from frappe_hr_pph21.setup import (COMPONENT_FIELDS, component_role, configure_accounts,
                                  create_components, component_has_submitted_slips, settings_has_submitted_slips)
from frappe_hr_pph21.tax.rules import RULE_VERSION


class PPh21Settings(Document):
    def validate(self):
        self.settings_name = (self.settings_name or '').strip()
        if not self.settings_name:
            frappe.throw('Isi Nama Pengaturan, misalnya PUP - Kantor atau PUP - Produksi.')
        old = self.get_doc_before_save()
        if old:
            frappe.db.sql('SELECT name FROM `tabPPh21 Settings` WHERE name=%s FOR UPDATE', (self.name,))
        if old and old.company != self.company:
            frappe.throw('Company Settings yang sudah tersimpan tidak dapat diubah; buat Settings baru.')
        for base, field in COMPONENT_FIELDS.items():
            # Legacy records keep their components; new records each own a distinct set.
            expected = old.get(field) if old and old.get(field) else f'{base} [{self.name}]'
            self.set(field, expected)
        if old and any(old.get(field) != self.get(field) for field in
                       ('expense_account', 'tax_payable_account', 'rounding')):
            if any(component_has_submitted_slips(self.get(field), self.company)
                   for field in COMPONENT_FIELDS.values()) or settings_has_submitted_slips(self.name):
                frappe.throw('Akun/pembulatan Settings sudah digunakan pada slip submitted; buat Settings baru.')
        self.rule_version = RULE_VERSION
        if frappe.db.get_value("Company", self.company, "default_currency") != "IDR":
            frappe.throw("Rilis ini hanya mendukung perusahaan dengan mata uang IDR.")
        for field, root in (("expense_account", "Expense"), ("tax_payable_account", "Liability")):
            account = frappe.get_doc("Account", self.get(field))
            if account.company != self.company or account.is_group or account.root_type != root:
                frappe.throw(f"{field}: pilih akun {root} non-group milik perusahaan ini.")
            if account.account_currency != "IDR" or account.get("disabled"):
                frappe.throw(f"{field}: akun harus aktif dengan currency IDR.")
        seen = set()
        for row in self.component_mapping:
            if component_role(row.salary_component) or row.salary_component in seen:
                frappe.throw("Pemetaan komponen duplikat atau menggunakan komponen otomatis PPh21.")
            seen.add(row.salary_component)
            component = frappe.get_doc("Salary Component", row.salary_component)
            row.component_abbr = component.salary_component_abbr
            if row.treatment in ("Taxable Cash", "Taxable Noncash", "Non Taxable") and component.type != "Earning":
                frappe.throw(f"{row.salary_component}: perlakuan ini hanya untuk Earning.")
            if row.treatment == "Annual Deduction" and component.type != "Deduction":
                frappe.throw(f"{row.salary_component}: pengurang tahunan harus Deduction.")
            if component.statistical_component and row.treatment != "Ignore":
                frappe.throw("Statistical Component tidak tersimpan pada slip v15. Gunakan Earning noncash sesuai panduan.")
            if component.variable_based_on_taxable_salary:
                frappe.throw("Jangan petakan komponen pajak standar ke PPh21; hapus dari struktur pegawai PPh21.")

    def on_update(self):
        create_components(self)
        configure_accounts(self)
