"""Workspace display migration; the app/module Python identity stays unchanged."""
import frappe

OLD_NAME = 'Frappe HR PPh21'
NAME = 'PPh 21'
MODULE = 'Frappe HR PPh21'


def before_migrate():
    # Rename before workspace JSON sync so upgrades do not create a second menu.
    existing = frappe.db.get_value('Workspace', NAME, ['module', 'public'], as_dict=True)
    if existing and (existing.module != MODULE or not existing.public):
        frappe.throw('Workspace PPh 21 sudah dipakai workspace lain. Ganti nama workspace tersebut sebelum migrate.')
    old = frappe.db.get_value('Workspace', OLD_NAME, ['module', 'public'], as_dict=True)
    if not old or old.module != MODULE or not old.public:
        return
    if not existing:
        # Migration runs as Administrator. The public v15 wrapper does not accept
        # ignore_permissions (that keyword belongs to the internal model function).
        frappe.rename_doc('Workspace', OLD_NAME, NAME, force=True)
        frappe.db.set_value('Workspace', NAME, {'label': NAME, 'title': NAME, 'parent_page': 'HR'})
    else:
        # Preserve any old custom content if both records already exist, but hide the duplicate menu.
        frappe.db.set_value('Workspace', OLD_NAME, 'is_hidden', 1)
    # parent_page is Data in v15, so rename_doc does not rewrite child workspace parents.
    for row in frappe.get_all('Workspace', filters={'parent_page': OLD_NAME, 'public': 1}, pluck='name'):
        frappe.db.set_value('Workspace', row, 'parent_page', NAME)


def sync_navigation():
    if frappe.db.exists('Workspace', NAME):
        frappe.db.set_value('Workspace', NAME,
                            {'label': NAME, 'title': NAME, 'parent_page': 'HR', 'is_hidden': 0})
        frappe.clear_cache(doctype='Workspace')
