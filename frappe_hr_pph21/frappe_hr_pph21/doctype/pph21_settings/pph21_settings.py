import frappe
from frappe.model.document import Document

from frappe_hr_pph21.setup import (ALLOWANCE, COMPONENT_FIELDS, component_role,
                                  settings_components, validate_component, is_tax_component, settings_has_submitted_slips,
                                  validate_noncash_component, component_account)
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
        selected = settings_components(self)
        changed = old and (old.rounding != self.rounding or any(
            old.get(field) != self.get(field) for field in COMPONENT_FIELDS.values()))
        if changed and settings_has_submitted_slips(self.name):
            frappe.throw('Pilihan komponen/pembulatan Settings sudah dipakai slip submitted; gunakan Settings baru.')
        sources = {r.salary_component for r in self.component_mapping}
        pairs = {r.get("noncash_offset_component") for r in self.component_mapping}
        for role, name in selected.items():
            if name in sources | pairs:
                frappe.throw("Komponen pajak tidak boleh sekaligus menjadi sumber mapping atau pasangan noncash.")
            component = validate_component(name, role=role, for_update=True)
            component_account(component, self.company,
                              "Expense" if role == ALLOWANCE else "Liability")
        self.rule_version = RULE_VERSION
        if frappe.db.get_value("Company", self.company, "default_currency") != "IDR":
            frappe.throw("Rilis ini hanya mendukung perusahaan dengan mata uang IDR.")
        # Once posted, preserve the noncash source/pair mapping used by the ledger.
        if old:
            current = {r.salary_component: r for r in self.component_mapping}
            for previous in old.component_mapping or []:
                before = (previous.treatment, previous.get("noncash_offset_component"))
                after = current.get(previous.salary_component)
                if previous.get("noncash_offset_component") and (not after or before != (after.treatment, after.get("noncash_offset_component"))) and settings_has_submitted_slips(self.name):
                    frappe.throw("Mapping noncash telah dipakai slip submitted; gunakan Settings baru atau koreksi slip terlebih dahulu.")
        seen = set()
        for row in self.component_mapping:
            if component_role(row.salary_component) or is_tax_component(row.salary_component) or row.salary_component in seen:
                frappe.throw("Pemetaan komponen duplikat atau menggunakan komponen pajak PPh21.")
            seen.add(row.salary_component)
            component = frappe.get_doc("Salary Component", row.salary_component)
            row.component_abbr = component.salary_component_abbr
            if row.treatment in ("Taxable Cash", "Taxable Noncash", "Non Taxable") and component.type != "Earning":
                frappe.throw(f"{row.salary_component}: perlakuan ini hanya untuk Earning.")
            if row.treatment == "Annual Deduction" and component.type != "Deduction":
                frappe.throw(f"{row.salary_component}: pengurang tahunan harus Deduction.")
            if component.statistical_component and row.treatment != "Ignore":
                frappe.throw("Statistical Component tidak tersimpan pada slip v15. Gunakan Earning noncash sesuai panduan.")
            needs_pair = row.treatment == "Taxable Noncash" or (
                component.type == "Earning" and component.do_not_include_in_total and not component.statistical_component
            )
            if needs_pair:
                if row.treatment not in ("Taxable Noncash", "Non Taxable", "Ignore") or not component.do_not_include_in_total:
                    frappe.throw(f"{row.salary_component}: noncash harus Do Not Include in Total, dengan mapping Taxable Noncash/Non Taxable/Ignore.")
                if component.get("only_tax_impact") or component.get("is_flexible_benefit"):
                    frappe.throw(f"{row.salary_component}: noncash BPJS tidak boleh Only Tax Impact atau Flexible Benefit.")
                if not row.get("noncash_offset_component"):
                    frappe.throw(f"{row.salary_component}: pilih Komponen Pasangan Noncash yang sudah ada di Salary Component.")
                if row.noncash_offset_component in sources:
                    frappe.throw("Komponen pasangan noncash tidak boleh sekaligus menjadi komponen sumber pada mapping.")
                offset = validate_noncash_component(row.noncash_offset_component)
                component_account(offset, self.company, "Liability")
            else:
                if row.get("noncash_offset_component"):
                    frappe.throw(f"{row.salary_component}: kosongkan Komponen Pasangan Noncash karena komponen ini bukan Earning noncash.")
            if component.variable_based_on_taxable_salary:
                frappe.throw("Jangan petakan komponen pajak standar ke PPh21; hapus dari struktur pegawai PPh21.")
