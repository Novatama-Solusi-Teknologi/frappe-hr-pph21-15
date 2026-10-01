"""One-time removal of unused legacy auto-generated noncash counterparts.

Not whitelisted. Called by a post-schema patch or by an administrator via bench.
Never force-deletes linked records or changes manual components/tax components.
"""
import json
import re

import frappe

from frappe_hr_pph21.setup import NONCASH_OFFSET, component_abbreviation, settings_has_submitted_slips


LEGACY_NAME = re.compile(re.escape(NONCASH_OFFSET) + r" \[[0-9a-f]{20}\]\Z")


def _usage_reason(component, mappings):
    name = component.name
    # Include draft and cancelled records: historical/setup references matter too.
    if frappe.db.exists("Salary Detail", {"salary_component": name}):
        return "Direferensikan Salary Slip atau Salary Structure (termasuk draft/cancelled)."
    if frappe.db.exists("Additional Salary", {"salary_component": name}):
        return "Direferensikan Additional Salary."
    if frappe.db.exists("PPh21 Component Tax Mapping", {"salary_component": name}):
        return "Dipakai sebagai komponen sumber pada mapping."
    for setting in sorted({r.parent for r in mappings}):
        if settings_has_submitted_slips(setting):
            return f"Settings {setting} sudah dipakai slip submitted."
    # Formula references use abbreviations and are not DocType Link fields.
    for doctype in ("Salary Component", "Salary Detail"):
        rows = frappe.get_all(doctype,
            filters={"name": ["!=", name]} if doctype == "Salary Component" else {},
            or_filters={"formula": ["like", f"%{component.salary_component_abbr}%"],
                        "condition": ["like", f"%{component.salary_component_abbr}%"]},
            fields=["name"], limit_page_length=1)
        if rows:
            return f"Abbreviation masih direferensikan formula/condition pada {doctype}."
    return None


def cleanup_unused_noncash(dry_run=True):
    """Return a report; dry_run performs no writes. Existing Accounts are not copied."""
    report = dict(dry_run=dry_run, eligible=[], deleted=[], skipped=[], cleared_mappings=[])
    candidates = frappe.get_all("Salary Component",
        filters={"name": ["like", NONCASH_OFFSET + " [%"]}, fields=["name"], order_by="name asc")
    for index, row in enumerate(candidates):
        if not LEGACY_NAME.fullmatch(row.name):
            report["skipped"].append(dict(component=row.name, reason="Nama bukan format pasangan legacy app."))
            continue
        mappings = frappe.get_all("PPh21 Component Tax Mapping",
            filters={"noncash_offset_component": row.name},
            fields=["name", "parent", "parenttype", "parentfield", "salary_component"])
        if any(r.parenttype != "PPh21 Settings" or r.parentfield != "component_mapping" for r in mappings):
            report["skipped"].append(dict(component=row.name, reason="Parent mapping tidak dikenal."))
            continue
        # Match submit's lock order: Settings before Salary Component.
        if not dry_run:
            for setting in sorted({r.parent for r in mappings}):
                frappe.get_doc("PPh21 Settings", setting, for_update=True)
        component = frappe.get_doc("Salary Component", row.name, for_update=not dry_run)
        if (component.salary_component_abbr != component_abbreviation(row.name)
                or component.type != "Deduction"
                or not str(component.get("description") or "").startswith("Pasangan jurnal otomatis ")):
            report["skipped"].append(dict(component=row.name, reason="Identitas master berbeda dari pasangan buatan app."))
            continue
        reason = _usage_reason(component, mappings)
        if reason:
            report["skipped"].append(dict(component=row.name, reason=reason))
            continue
        report["eligible"].append(row.name)
        if dry_run:
            continue
        savepoint = f"pph21_cleanup_{index}"
        frappe.db.savepoint(savepoint)
        try:
            for mapping in mappings:
                frappe.db.set_value("PPh21 Component Tax Mapping", mapping.name,
                    "noncash_offset_component", None, update_modified=False)
            # Retain native link checks, on_trash hooks and Deleted Document archive.
            frappe.delete_doc("Salary Component", row.name, ignore_permissions=True,
                              force=False, delete_permanently=False)
        except frappe.LinkExistsError:
            frappe.db.rollback(save_point=savepoint)
            report["eligible"].remove(row.name)
            report["skipped"].append(dict(component=row.name, reason="Masih ada referensi lain; mapping dipulihkan dan master dipertahankan."))
            continue
        report["deleted"].append(row.name)
        report["cleared_mappings"].extend(dict(mapping=r.name, settings=r.parent,
            source_component=r.salary_component, previous_pair=row.name) for r in mappings)
        for setting in {r.parent for r in mappings}:
            frappe.clear_document_cache("PPh21 Settings", setting)
    return report


def run_cleanup_patch():
    report = cleanup_unused_noncash(dry_run=False)
    if report["deleted"] or report["skipped"]:
        # Private attachment for the site administrator, including why records were skipped.
        frappe.get_doc(dict(doctype="File", file_name="pph21-noncash-cleanup-0.8.1.json",
            is_private=1, content=json.dumps(report, ensure_ascii=False, indent=2))).insert(ignore_permissions=True)
    return report
