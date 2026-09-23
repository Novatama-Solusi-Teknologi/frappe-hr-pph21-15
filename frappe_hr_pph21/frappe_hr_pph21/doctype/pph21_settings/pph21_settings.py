import frappe
from frappe.model.document import Document

from frappe_hr_pph21.setup import COMPONENTS, configure_accounts
from frappe_hr_pph21.tax.rules import RULE_VERSION


class PPh21Settings(Document):
    def validate(self):
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
            if row.salary_component in COMPONENTS or row.salary_component in seen:
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
        old = self.get_doc_before_save()
        if old and old.rounding != self.rounding and frappe.db.exists(
            "Salary Slip", {"company": self.company, "docstatus": 1, "pph21_tax_profile": ["is", "set"]}
        ):
            frappe.throw("Pembulatan sudah digunakan pada slip submitted; pertahankan agar rekonsiliasi konsisten.")

    def on_update(self):
        configure_accounts(self)
