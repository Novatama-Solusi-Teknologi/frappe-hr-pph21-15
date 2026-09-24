"""Permission-aware lookups used only by this app's forms."""
import re

import frappe
from frappe.utils import cint

from frappe_hr_pph21.tax.rules import PTKP


def bulk_profile_permission(doc, user=None, ptype=None):
    # A batch may span companies. Reading it must not expose another company's NIK.
    # This hook only restricts access; normal DocType permissions still apply.
    return all(frappe.has_permission('Employee', 'read', doc=row.employee, user=user)
               for row in (doc.get('employees') or []) if row.employee)


def employee_values(employee):
    doc = frappe.get_doc('Employee', employee)
    doc.check_permission('read')
    raw = re.sub(r'\s+', '', str(doc.get('custom_ptkp') or '')).upper()
    match = re.fullmatch(r'(TK|K)/?([0-3])', raw)
    status = '/'.join(match.groups()) if match else ''
    return dict(company=doc.company, employee_name=doc.employee_name,
                ptkp_status=status if status in PTKP else '')


@frappe.whitelist()
def employee_tax_defaults(employee):
    frappe.only_for(['HR Manager', 'System Manager'])
    return employee_values(employee)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def salary_component_query(doctype, txt, searchfield, start, page_len, filters=None):
    # Fixed fields and get_list preserve Frappe role/User Permission filtering.
    from frappe_hr_pph21.setup import COMPONENTS

    rows = frappe.get_list(
        'Salary Component', fields=['name', 'salary_component_abbr', 'type'],
        filters=[['name', 'not in', list(COMPONENTS)], ['disabled', '=', 0]]
        + [['name', 'not like', base + ' [%'] for base in COMPONENTS],
        or_filters={'name': ['like', f'%{txt}%'], 'salary_component_abbr': ['like', f'%{txt}%']},
        start=max(0, cint(start)), page_length=min(50, max(1, cint(page_len))), order_by='name asc',
    )
    return [[row.name, row.salary_component_abbr, row.type] for row in rows]
