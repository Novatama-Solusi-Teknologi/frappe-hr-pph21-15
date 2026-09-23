frappe.query_reports["PPh21 Register"] = {
    filters: [
        {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", reqd: 1,
            default: frappe.defaults.get_user_default("Company")},
        {fieldname: "tax_year", label: __("Tahun Pajak"), fieldtype: "Int", reqd: 1, default: new Date().getFullYear()},
        {fieldname: "month", label: __("Masa"), fieldtype: "Select", options: "\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n11\n12"},
        {fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee"},
    ],
};
