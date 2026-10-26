"""Backfill a unique payable account from legacy counterparts, without guessing."""
import json

import frappe

from frappe_hr_pph21.setup import sync_custom_fields, component_account


def execute():
    sync_custom_fields()
    candidates, report = {}, dict(copied=[], skipped=[])
    for setting in frappe.get_all("PPh21 Settings", fields=["name", "company"]):
        doc = frappe.get_doc("PPh21 Settings", setting.name)
        for row in doc.component_mapping:
            if not row.get("noncash_offset_component"):
                continue
            key = (row.salary_component, doc.company)
            candidates.setdefault(key, set()).add(row.noncash_offset_component)
    for (source, company), pairs in sorted(candidates.items()):
        try:
            component = frappe.get_doc("Salary Component", source, for_update=True)
            if component.type != "Earning" or not component.do_not_include_in_total or component.statistical_component:
                raise ValueError("Sumber bukan Earning noncash.")
            component_account(component, company, "Expense")
            accounts = {component_account(frappe.get_doc("Salary Component", pair), company, "Liability") for pair in pairs}
            if len(accounts) != 1:
                raise ValueError("Beberapa Settings memakai akun utang berbeda untuk sumber/Company yang sama; pilih manual.")
            payable = accounts.pop()
            target = next(r for r in component.accounts if r.company == company)
            existing = target.get("pph21_noncash_payable_account")
            if existing and existing != payable:
                raise ValueError("Akun Utang Noncash sudah diisi berbeda; tidak ditimpa.")
            if not existing:
                frappe.db.set_value("Salary Component Account", target.name,
                    "pph21_noncash_payable_account", payable, update_modified=False)
                frappe.clear_document_cache("Salary Component", source)
                report["copied"].append(dict(component=source, company=company, payable_account=payable))
        except (frappe.ValidationError, frappe.DoesNotExistError, ValueError) as exc:
            report["skipped"].append(dict(component=source, company=company, reason=str(exc)))
    if report["copied"] or report["skipped"]:
        frappe.get_doc(dict(doctype="File", file_name="pph21-noncash-accounts-0.10.0.json",
            is_private=1, content=json.dumps(report, ensure_ascii=False, indent=2))).insert(ignore_permissions=True)
    return report
