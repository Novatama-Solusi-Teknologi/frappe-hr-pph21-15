"""Idempotent installation; no Company, employee, account or payroll is activated."""

from hashlib import sha256

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


ALLOWANCE = "PPh21 Tunjangan Pajak"
WITHHOLDING = "PPh21 Potongan Pajak"
REFUND = "PPh21 Pengembalian Pajak"
COMPONENTS = {
    ALLOWANCE: ("Earning", "PPH21_TAX_ALLOW", 1),
    WITHHOLDING: ("Deduction", "PPH21_TAX", 0),
    REFUND: ("Earning", "PPH21_TAX_REFUND", 0),
}
NONCASH_OFFSET = "PPh21 Utang Noncash"

COMPONENT_FIELDS = {ALLOWANCE: 'allowance_component', WITHHOLDING: 'withholding_component',
                    REFUND: 'refund_component'}


def component_role(name):
    if str(name).startswith(NONCASH_OFFSET + " [") and str(name).endswith("]"):
        return NONCASH_OFFSET
    return next((base for base in COMPONENTS if name == base or
                 (str(name).startswith(base + ' [') and str(name).endswith(']'))), None)


def component_abbreviation(name):
    base = component_role(name)
    if not base:
        frappe.throw('Komponen bukan komponen otomatis PPh21.')
    abbr = "PPH21_NC" if base == NONCASH_OFFSET else COMPONENTS[base][1]
    return abbr if name == base else abbr + '_' + sha256(name.encode()).hexdigest()[:12]


def settings_components(settings):
    result = {base: settings.get(field) for base, field in COMPONENT_FIELDS.items()}
    if any(not name for name in result.values()):
        frappe.throw("Pilih komponen Tunjangan, Potongan, dan Pengembalian PPh21 pada Settings.")
    if len(set(result.values())) != len(result):
        frappe.throw("Tunjangan, Potongan, dan Pengembalian PPh21 harus memakai tiga komponen berbeda.")
    return result


def component_has_submitted_slips(name, company=None):
    return bool(frappe.db.sql(
        'SELECT ss.name FROM `tabSalary Slip` ss JOIN `tabSalary Detail` sd ON sd.parent=ss.name '
        'WHERE sd.parenttype=\'Salary Slip\' AND sd.salary_component=%s AND ss.docstatus=1 '
        + ('AND ss.company=%s ' if company else '') + 'LIMIT 1 FOR UPDATE',
        (name, company) if company else (name,),
    ))


def settings_has_submitted_slips(name):
    # The profile join includes legacy and zero-tax slips without generated detail rows.
    return bool(frappe.db.sql(
        'SELECT ss.name FROM `tabSalary Slip` ss '
        'LEFT JOIN `tabPPh21 Employee Tax Profile` p ON p.name=ss.pph21_tax_profile '
        'WHERE ss.docstatus=1 AND (ss.pph21_tax_settings=%s OR p.pph21_settings=%s) '
        'LIMIT 1 FOR UPDATE', (name, name),
    ))


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


def after_migrate():
    check_versions()
    sync_custom_fields()
    sync_mapping_codes()
    from frappe_hr_pph21.fiscal_year import backfill_fiscal_year_links
    backfill_fiscal_year_links()
    from frappe_hr_pph21.settings import migrate_settings_links
    migrate_settings_links()
    from frappe_hr_pph21.workspace import sync_navigation
    sync_navigation()


def sync_mapping_codes():
    """Populate display metadata on existing mappings without saving payroll/settings."""
    for row in frappe.get_all('PPh21 Component Tax Mapping',
                              fields=['name', 'salary_component', 'component_abbr']):
        abbr = frappe.db.get_value('Salary Component', row.salary_component, 'salary_component_abbr')
        if row.component_abbr != abbr:
            frappe.db.set_value('PPh21 Component Tax Mapping', row.name,
                                'component_abbr', abbr, update_modified=False)


def sync_custom_fields():
    fields = [dict(fieldname="pph21_tax_section", label="PPh 21", fieldtype="Section Break",
                   insert_after="base_total_in_words", collapsible=1)]
    specs = [
        ("pph21_tax_profile", "Profil Pajak PPh21", "Link", "PPh21 Employee Tax Profile"),
        ("pph21_tax_settings", "PPh21 Settings", "Link", "PPh21 Settings"),
        ("pph21_tax_year", "Tahun Pajak", "Int", None),
        ("pph21_tax_payment_date", "Tanggal Pembayaran (Posting Date)", "Date", None),
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
        ("pph21_tax_worksheet", "Ringkasan Kertas Kerja", "HTML", None),
        ("pph21_tax_snapshot", "Kertas Kerja Pajak (JSON)", "Code", "JSON"),
    ]
    previous = "pph21_tax_section"
    layout = {
        "pph21_tax_category": ("pph21_identity_column", "Column Break", None),
        "pph21_tax_rule": ("pph21_rule_column", "Column Break", None),
        "pph21_tax_base": ("pph21_amounts_section", "Section Break", "Perhitungan PPh21"),
        "pph21_tax_allowance": ("pph21_allowance_column", "Column Break", None),
        "pph21_tax_refund": ("pph21_refund_column", "Column Break", None),
        "pph21_tax_worksheet": ("pph21_snapshot_section", "Section Break", "Kertas Kerja PPh21"),
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
        if name == "pph21_tax_snapshot":
            item["hidden"] = 1
        fields.append(item)
        previous = name
    create_custom_fields({
        "Employee": [dict(fieldname="pph21_enabled", label="PPh21 Enabled", fieldtype="Check",
                          default="0", insert_after="employment_type",
                          description="Memerlukan profil pajak PPh21 per tahun dan pengaturan perusahaan.")],
        "Salary Slip": fields,
    }, update=True)


def tax_component_roles(name):
    """Identify selected masters by Settings links, independent of their names."""
    if not name:
        return set()
    return {role for role, field in COMPONENT_FIELDS.items()
            if frappe.db.exists("PPh21 Settings", {field: name})}


def is_tax_component(name):
    return bool(tax_component_roles(name))


def validate_component(name, for_update=False, role=None):
    """Validate an existing tax master for its selected role; never rewrite it."""
    role = role or component_role(name)
    if role not in COMPONENTS:
        frappe.throw("Tentukan peran komponen pajak pada PPh21 Settings.")
    doc = frappe.get_doc("Salary Component", name, for_update=for_update)
    kind, _, taxable = COMPONENTS[role]
    if tax_component_roles(name) - {role}:
        frappe.throw(f"{name}: sudah dipakai untuk peran pajak lain pada Settings. Gunakan komponen berbeda.")
    if is_noncash_offset(name) or frappe.db.exists("PPh21 Component Tax Mapping", {"salary_component": name}):
        frappe.throw(f"{name}: komponen pajak tidak boleh dipakai sebagai sumber mapping atau pasangan noncash.")
    expected = dict(type=kind, is_tax_applicable=taxable,
                    depends_on_payment_days=0, variable_based_on_taxable_salary=0,
                    statistical_component=0, do_not_include_in_total=0,
                    is_flexible_benefit=0, amount_based_on_formula=0,
                    only_tax_impact=0, do_not_include_in_accounts=0, disabled=0)
    for field, value in expected.items():
        actual = doc.get(field) or (0 if isinstance(value, int) else "")
        if actual != value:
            frappe.throw(f"Salary Component {name}: {field} harus {value!r} untuk {role}.")
    if not doc.salary_component_abbr or doc.get("formula") or doc.get("condition") or doc.get("amount"):
        frappe.throw(f"Salary Component {name}: isi abbreviation; Amount nol, formula/condition kosong. Nominal pajak dihitung app.")
    return doc


def noncash_component_name(settings_name, source_component):
    token = sha256(f"{settings_name}|{source_component}".encode()).hexdigest()[:20]
    return f"{NONCASH_OFFSET} [{token}]"


def validate_noncash_account(name, company, root_type, for_update=False):
    if not name:
        frappe.throw(f"Lengkapi akun {root_type} untuk Company {company}.")
    account = frappe.get_doc("Account", name, for_update=for_update)
    if (account.company != company or account.root_type != root_type or account.is_group
            or account.get("disabled") or account.account_currency != "IDR"):
        frappe.throw(f"Akun {name}: harus {root_type}, aktif, non-group, IDR, milik Company {company}.")
    return name


def component_account(component, company, root_type, for_update=False):
    rows = [row for row in component.accounts if row.company == company]
    if len(rows) != 1 or not rows[0].account:
        frappe.throw(f"Salary Component {component.name}: isi tepat satu akun {root_type} pada tabel Accounts untuk {company}.")
    return validate_noncash_account(rows[0].account, company, root_type, for_update)


def validate_noncash_component(name, for_update=False):
    """Validate a user-selected journal counterpart without changing its master."""
    if not name:
        frappe.throw("Pilih Komponen Pasangan Noncash pada mapping PPh21 Settings.")
    role = component_role(name)
    if (role and role != NONCASH_OFFSET) or is_tax_component(name):
        frappe.throw("Komponen pajak PPh21 tidak dapat digunakan sebagai pasangan noncash.")
    doc = frappe.get_doc("Salary Component", name, for_update=for_update)
    expected = dict(type="Deduction", depends_on_payment_days=0,
        variable_based_on_taxable_salary=0, statistical_component=0,
        do_not_include_in_total=1, do_not_include_in_accounts=0,
        is_tax_applicable=0, is_flexible_benefit=0, only_tax_impact=0,
        amount_based_on_formula=0, disabled=0)
    for field, value in expected.items():
        actual = doc.get(field) or (0 if isinstance(value, int) else "")
        if actual != value:
            frappe.throw(f"Salary Component {name}: {field} harus {value!r} untuk pasangan noncash. Gunakan komponen khusus jurnal, bukan potongan tunai pegawai.")
    if not doc.salary_component_abbr or doc.get("formula") or doc.get("condition") or doc.get("amount"):
        frappe.throw(f"Salary Component {name}: pasangan noncash memerlukan abbreviation; Amount harus nol, formula/condition kosong. Nominal mengikuti sumber noncash.")
    return doc


def is_noncash_offset(name):
    return bool(name and frappe.db.exists("PPh21 Component Tax Mapping", {
        "noncash_offset_component": name,
    }))
