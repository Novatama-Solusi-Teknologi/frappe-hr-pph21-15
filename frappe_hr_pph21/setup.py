"""Idempotent installation; no Company, employee, account or payroll is activated."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from frappe_hr_pph21.tax.rules import RULE_VERSION

ALLOWANCE = "PPh21 Tunjangan Pajak"
WITHHOLDING = "PPh21 Potongan Pajak"
REFUND = "PPh21 Pengembalian Pajak"
COMPONENTS = {
    ALLOWANCE: ("Earning", "PPH21_TAX_ALLOW", 1),
    WITHHOLDING: ("Deduction", "PPH21_TAX", 0),
    REFUND: ("Earning", "PPH21_TAX_REFUND", 0),
}


def check_versions():
    import erpnext
    import hrms

    for name, version in (("frappe", frappe.__version__), ("erpnext", erpnext.__version__),
                          ("hrms", hrms.__version__)):
        if str(version).split('.')[0] != "15":
            frappe.throw(f"Frappe HR PPh21 memerlukan {name} v15; ditemukan {version}.")
    overrides = frappe.get_hooks("override_doctype_class").get("Salary Slip", [])
    expected = "frappe_hr_pph21.overrides.salary_slip.PPh21SalarySlip"
    if any(path != expected for path in overrides):
        frappe.throw("Ada app lain yang override Salary Slip. Gabungkan integrasi sebelum install Frappe HR PPh21.")


def after_install():
    sync_custom_fields()
    create_components()


def after_migrate():
    check_versions()
    sync_custom_fields()
    create_components()
    sync_mapping_codes()
    from frappe_hr_pph21.fiscal_year import backfill_fiscal_year_links
    backfill_fiscal_year_links()


def sync_mapping_codes():
    """Populate display metadata on existing mappings without saving payroll/settings."""
    for row in frappe.get_all('PPh21 Component Tax Mapping',
                              fields=['name', 'salary_component', 'component_abbr']):
        abbr = frappe.db.get_value('Salary Component', row.salary_component, 'salary_component_abbr')
        if row.component_abbr != abbr:
            frappe.db.set_value('PPh21 Component Tax Mapping', row.name,
                                'component_abbr', abbr, update_modified=False)


def sync_custom_fields():
    fields = [dict(fieldname="pph21_tax_section", label="Frappe HR PPh21", fieldtype="Section Break",
                   insert_after="base_total_in_words", collapsible=1)]
    specs = [
        ("pph21_tax_profile", "Profil Pajak PPh21", "Link", "PPh21 Employee Tax Profile"),
        ("pph21_tax_year", "Tahun Pajak", "Int", None),
        ("pph21_tax_month", "Masa Pajak", "Int", None),
        ("pph21_tax_final", "Masa Pajak Terakhir", "Check", None),
        ("pph21_tax_category", "Kategori TER", "Data", None),
        ("pph21_tax_method", "Metode Pajak", "Data", None),
        ("pph21_tax_rule", "Versi Aturan", "Data", None),
        ("pph21_tax_base", "Bruto sebelum Tunjangan Pajak", "Currency", "IDR"),
        ("pph21_tax_gross", "Bruto PPh 21 Masa Ini", "Currency", "IDR"),
        ("pph21_tax_deductions", "Pengurang Tahunan Masa Ini", "Currency", "IDR"),
        ("pph21_tax_allowance", "Tunjangan PPh 21", "Currency", "IDR"),
        ("pph21_tax_withholding", "PPh 21 Dipotong", "Currency", "IDR"),
        ("pph21_tax_refund", "PPh 21 Dikembalikan", "Currency", "IDR"),
        ("pph21_tax_rate", "Tarif TER (%)", "Percent", None),
        ("pph21_tax_annual", "PPh Setahun (Masa Terakhir)", "Currency", "IDR"),
        ("pph21_tax_key", "Kunci Masa Pajak", "Data", None),
        ("pph21_tax_snapshot", "Kertas Kerja Pajak (JSON)", "Code", "JSON"),
    ]
    previous = "pph21_tax_section"
    layout = {
        "pph21_tax_category": ("pph21_identity_column", "Column Break", None),
        "pph21_tax_rule": ("pph21_rule_column", "Column Break", None),
        "pph21_tax_base": ("pph21_amounts_section", "Section Break", "Perhitungan PPh21"),
        "pph21_tax_allowance": ("pph21_allowance_column", "Column Break", None),
        "pph21_tax_refund": ("pph21_refund_column", "Column Break", None),
        "pph21_tax_snapshot": ("pph21_snapshot_section", "Section Break", "Kertas Kerja PPh21"),
    }
    for name, label, kind, options in specs:
        if name in layout:
            fieldname, fieldtype, title = layout[name]
            layout_field = dict(fieldname=fieldname, fieldtype=fieldtype,
                                insert_after=previous, print_hide=1)
            if title:
                layout_field.update(label=title, collapsible=1)
            fields.append(layout_field)
            previous = fieldname
        item = dict(fieldname=name, label=label, fieldtype=kind, read_only=1,
                    no_copy=1, insert_after=previous, print_hide=1)
        if options:
            item["options"] = "currency" if kind == "Currency" else options
        if kind in ("Currency", "Percent"):
            item["precision"] = "2" if kind == "Currency" else "4"
        if name == "pph21_tax_key":
            item.update(hidden=1, unique=1, allow_on_submit=1)
        fields.append(item)
        previous = name
    create_custom_fields({
        "Employee": [dict(fieldname="pph21_enabled", label="PPh21 Enabled", fieldtype="Check",
                          default="0", insert_after="employment_type",
                          description="Memerlukan profil pajak PPh21 per tahun dan pengaturan perusahaan.")],
        "Salary Slip": fields,
    }, update=True)


def create_components():
    for name, (kind, abbr, taxable) in COMPONENTS.items():
        if frappe.db.exists("Salary Component", name):
            continue  # Never overwrite the site's accounts or settings during migrate.
        frappe.get_doc(dict(doctype="Salary Component", salary_component=name,
                            salary_component_abbr=abbr, type=kind,
                            is_tax_applicable=taxable, depends_on_payment_days=0,
                            variable_based_on_taxable_salary=0, statistical_component=0,
                            do_not_include_in_total=0, remove_if_zero_valued=1,
                            description=f"Dihitung otomatis Frappe HR PPh21 ({RULE_VERSION}); jangan masukkan ke Salary Structure/Additional Salary."
                            )).insert(ignore_permissions=True)


def validate_component(name):
    doc = frappe.get_doc("Salary Component", name)
    kind, abbr, taxable = COMPONENTS[name]
    expected = dict(type=kind, salary_component_abbr=abbr, is_tax_applicable=taxable,
                    depends_on_payment_days=0, variable_based_on_taxable_salary=0,
                    statistical_component=0, do_not_include_in_total=0,
                    is_flexible_benefit=0, amount_based_on_formula=0,
                    only_tax_impact=0, do_not_include_in_accounts=0)
    for field, value in expected.items():
        actual = doc.get(field) or (0 if isinstance(value, int) else "")
        if actual != value:
            frappe.throw(f"Salary Component {name}: {field} harus {value!r} untuk Frappe HR PPh21.")
    if doc.get("formula") or doc.get("condition"):
        frappe.throw(f"Hapus formula/condition pada komponen otomatis {name}.")
    return doc


def configure_accounts(settings):
    for name in COMPONENTS:
        component = validate_component(name)
        account = settings.expense_account if name == ALLOWANCE else settings.tax_payable_account
        rows = [row for row in component.accounts if row.company == settings.company]
        if len(rows) > 1:
            frappe.throw(f"Duplikasi account pada {name} untuk {settings.company}.")
        if rows:
            rows[0].default_account = account
        else:
            component.append("accounts", {"company": settings.company, "default_account": account})
        component.save(ignore_permissions=True)
