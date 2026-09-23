"""Resolve a PPh21 calendar year from ERPNext's Fiscal Year master."""
from datetime import date

import frappe
from frappe.utils import getdate

from frappe_hr_pph21.tax.rules import SUPPORTED_YEARS


def calendar_year(doc):
    if not doc.get('year_start_date') or not doc.get('year_end_date'):
        return None
    start, end = getdate(doc.year_start_date), getdate(doc.year_end_date)
    if start == date(start.year, 1, 1) and end == date(start.year, 12, 31):
        return start.year
    return None


def tax_year_from_fiscal_year(name, company=None):
    if not name:
        frappe.throw('Pilih Fiscal Year dari master ERPNext.')
    doc = frappe.get_doc('Fiscal Year', name)
    doc.check_permission('read')
    if doc.disabled:
        frappe.throw('Fiscal Year yang dipilih tidak aktif.')
    year = calendar_year(doc)
    if year is None:
        frappe.throw('PPh21 memerlukan Fiscal Year 1 Januari sampai 31 Desember pada tahun yang sama.')
    if year not in SUPPORTED_YEARS:
        frappe.throw('Fiscal Year di luar tahun pajak yang didukung: 2024-2026.')
    companies = {row.company for row in (doc.get('companies') or [])}
    if company and companies and company not in companies:
        frappe.throw('Fiscal Year tidak berlaku untuk Company pegawai yang dipilih.')
    return year


def backfill_fiscal_year_links():
    """Only add an unambiguous master link; never rewrite numeric years or payroll history."""
    masters = []
    for row in frappe.get_all('Fiscal Year', filters={'disabled': 0}, pluck='name'):
        doc = frappe.get_doc('Fiscal Year', row)
        year = calendar_year(doc)
        if year in SUPPORTED_YEARS:
            masters.append((doc.name, year, {c.company for c in (doc.get('companies') or [])}))

    def choose(year, companies):
        matches = [name for name, fiscal_year, allowed in masters
                   if fiscal_year == year and (not allowed or (companies and companies <= allowed))]
        return matches[0] if len(matches) == 1 else None

    for dt in ('PPh21 Employee Tax Profile', 'Bulk PPh21 Employee Tax Profile Row'):
        for row in frappe.get_all(dt, filters={'fiscal_year': ['is', 'not set']},
                                  fields=['name', 'tax_year', 'company']):
            name = choose(row.tax_year, {row.company} if row.company else set())
            if name:
                frappe.db.set_value(dt, row.name, 'fiscal_year', name, update_modified=False)
    for row in frappe.get_all('Bulk PPh21 Employee Tax Profile',
                              filters={'default_fiscal_year': ['is', 'not set']},
                              fields=['name', 'default_tax_year']):
        companies = set(frappe.get_all('Bulk PPh21 Employee Tax Profile Row',
                        filters={'parent': row.name, 'parenttype': 'Bulk PPh21 Employee Tax Profile'},
                        pluck='company')) - {None, ''}
        name = choose(row.default_tax_year, companies)
        if name:
            frappe.db.set_value('Bulk PPh21 Employee Tax Profile', row.name,
                                'default_fiscal_year', name, update_modified=False)
