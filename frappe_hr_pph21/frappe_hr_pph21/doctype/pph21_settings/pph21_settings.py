import frappe
from frappe.model.document import Document

from frappe_hr_pph21.setup import (COMPONENT_FIELDS, component_role,
                                  create_components, component_has_submitted_slips, settings_has_submitted_slips,
                                  noncash_component_name,
                                  configure_noncash_components)
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
        if old and old.rounding != self.rounding:
            if any(component_has_submitted_slips(self.get(field), self.company)
                   for field in COMPONENT_FIELDS.values()) or settings_has_submitted_slips(self.name):
                frappe.throw('Pembulatan Settings sudah digunakan pada slip submitted; buat Settings baru.')
        self.rule_version = RULE_VERSION
        if frappe.db.get_value("Company", self.company, "default_currency") != "IDR":
            frappe.throw("Rilis ini hanya mendukung perusahaan dengan mata uang IDR.")
        # Once posted, preserve the noncash source/pair mapping used by the ledger.
        if old:
            current = {r.salary_component: r for r in self.component_mapping}
            for previous in old.component_mapping or []:
                before = previous.treatment
                after = current.get(previous.salary_component)
                if previous.get("noncash_offset_component") and (not after or before != after.treatment) and component_has_submitted_slips(previous.noncash_offset_component, self.company):
                    frappe.throw("Mapping noncash telah dipakai slip submitted; gunakan Settings baru atau koreksi slip terlebih dahulu.")
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
            needs_pair = row.treatment == "Taxable Noncash" or (
                component.type == "Earning" and component.do_not_include_in_total and not component.statistical_component
            )
            if needs_pair:
                if row.treatment not in ("Taxable Noncash", "Non Taxable", "Ignore") or not component.do_not_include_in_total:
                    frappe.throw(f"{row.salary_component}: noncash harus Do Not Include in Total, dengan mapping Taxable Noncash/Non Taxable/Ignore.")
                if component.get("only_tax_impact") or component.get("is_flexible_benefit"):
                    frappe.throw(f"{row.salary_component}: noncash BPJS tidak boleh Only Tax Impact atau Flexible Benefit.")
                row.noncash_offset_component = noncash_component_name(self.name, row.salary_component)
            else:
                row.noncash_offset_component = None
            if component.variable_based_on_taxable_salary:
                frappe.throw("Jangan petakan komponen pajak standar ke PPh21; hapus dari struktur pegawai PPh21.")

    def on_update(self):
        create_components(self)
        configure_noncash_components(self)
