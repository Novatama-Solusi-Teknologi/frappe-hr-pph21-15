from frappe_hr_pph21.noncash_migration import execute as migrate_accounts


def execute():
    return migrate_accounts()
