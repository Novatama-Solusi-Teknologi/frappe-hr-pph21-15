"""Explicit per-profile settings selection; never pick an arbitrary company match."""
import frappe


def selected_settings(name, company, check_permission=True, for_update=False):
    if not name:
        frappe.throw('Pilih PPh21 Settings pada profil pajak pegawai.')
    doc = frappe.get_doc('PPh21 Settings', name, for_update=for_update)
    if check_permission:
        doc.check_permission('read')
    if doc.company != company:
        frappe.throw('PPh21 Settings harus berasal dari Company pegawai yang sama.')
    if not doc.enabled:
        frappe.throw('Aktifkan PPh21 Settings yang dipilih pada profil pegawai.')
    return doc


def default_settings(company):
    rows = frappe.get_list('PPh21 Settings', filters={'company': company, 'enabled': 1},
                           pluck='name', page_length=2)
    return rows[0] if len(rows) == 1 else None


def migrate_settings_links():
    """Preserve legacy component identities and attach unambiguous company profiles."""
    from frappe_hr_pph21.setup import COMPONENT_FIELDS

    by_company = {}
    for row in frappe.get_all('PPh21 Settings', fields=['name', 'company', 'settings_name']):
        by_company.setdefault(row.company, []).append(row.name)
        if not row.settings_name:
            values = {'settings_name': f'{row.company} - Standar'}
            # Before v0.4, the record name was exactly Company and components were shared.
            if row.name == row.company:
                values.update({field: base for base, field in COMPONENT_FIELDS.items()})
            frappe.db.set_value('PPh21 Settings', row.name, values, update_modified=False)
    for doctype in ('PPh21 Employee Tax Profile', 'Bulk PPh21 Employee Tax Profile Row'):
        for row in frappe.get_all(doctype, fields=['name', 'company', 'pph21_settings']):
            candidates = by_company.get(row.company, [])
            if not row.pph21_settings and len(candidates) == 1:
                frappe.db.set_value(doctype, row.name, 'pph21_settings', candidates[0], update_modified=False)
