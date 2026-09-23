import frappe


def execute(filters=None):
    filters = frappe._dict(filters or {})
    frappe.only_for(("HR Manager", "System Manager"))
    if not filters.company or not filters.tax_year:
        frappe.throw("Pilih Company dan Tahun Pajak.")
    query = {"company": filters.company, "pph21_tax_year": int(filters.tax_year), "docstatus": 1,
             "pph21_tax_profile": ["is", "set"]}
    if filters.get("month"):
        query["pph21_tax_month"] = int(filters.month)
    if filters.get("employee"):
        query["employee"] = filters.employee
    columns = [
        {"fieldname": "name", "label": "Salary Slip", "fieldtype": "Link", "options": "Salary Slip", "width": 190},
        {"fieldname": "employee", "label": "Employee", "fieldtype": "Link", "options": "Employee", "width": 150},
        {"fieldname": "employee_name", "label": "Nama", "fieldtype": "Data", "width": 160},
        {"fieldname": "pph21_tax_month", "label": "Masa", "fieldtype": "Int", "width": 60},
        {"fieldname": "pph21_tax_final", "label": "Terakhir", "fieldtype": "Check", "width": 75},
        {"fieldname": "pph21_tax_category", "label": "TER", "fieldtype": "Data", "width": 60},
        {"fieldname": "pph21_tax_method", "label": "Metode", "fieldtype": "Data", "width": 100},
        {"fieldname": "pph21_tax_rate", "label": "Tarif TER (%)", "fieldtype": "Percent", "width": 110},
    ]
    for name, label in (("base", "Bruto sebelum tunjangan"), ("allowance", "Tunjangan Pajak"),
                        ("gross", "Bruto PPh 21"), ("deductions", "Pengurang Tahunan Masa Ini"),
                        ("withholding", "PPh Dipotong"), ("refund", "Pengembalian"),
                        ("annual", "PPh Setahun (masa terakhir)")):
        columns.append({"fieldname": "pph21_tax_" + name, "label": label,
                        "fieldtype": "Currency", "options": "IDR", "width": 180})
    # get_list preserves Salary Slip user permissions, including Company restrictions.
    data = frappe.get_list("Salary Slip", filters=query, fields=[c["fieldname"] for c in columns],
                           order_by="employee asc, pph21_tax_month asc", limit_page_length=0)
    message = "Kertas kerja internal; bukan berkas impor Coretax/bukti potong resmi. Hanya slip submitted. Saldo awal tersedia pada profil dan snapshot slip."
    return columns, data, message
