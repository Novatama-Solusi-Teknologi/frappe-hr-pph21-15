import frappe

from frappe_hr_pph21.tax.rules import RULE_VERSION, TER


def execute(filters=None):
    frappe.only_for(("HR Manager", "System Manager"))
    columns = [
        {"fieldname": "category", "label": "Kategori", "fieldtype": "Data", "width": 100},
        {"fieldname": "lower", "label": "Di atas (baris pertama: mulai 0)", "fieldtype": "Currency", "options": "IDR", "width": 250},
        {"fieldname": "upper", "label": "Sampai dengan", "fieldtype": "Currency", "options": "IDR", "width": 200},
        {"fieldname": "rate", "label": "Tarif (%)", "fieldtype": "Percent", "width": 120},
        {"fieldname": "note", "label": "Keterangan", "fieldtype": "Data", "width": 200},
    ]
    data = []
    for category, bands in TER.items():
        lower = 0
        for upper, rate in bands:
            data.append(dict(category=category, lower=float(lower), upper=float(upper) if upper is not None else None,
                             rate=float(rate * 100), note="Tanpa batas atas" if upper is None else ""))
            lower = upper
    return columns, data, f"Master {RULE_VERSION}. Batas atas inklusif. Sumber: Lampiran PP 58/2023."
