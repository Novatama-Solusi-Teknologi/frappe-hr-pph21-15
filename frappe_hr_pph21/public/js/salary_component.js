frappe.ui.form.on("Salary Component", {
    setup(frm) {
        frm.set_query("pph21_noncash_payable_account", "accounts", (doc, cdt, cdn) => ({
            filters: {company: locals[cdt][cdn].company || "", root_type: "Liability",
                is_group: 0, disabled: 0, account_currency: "IDR"},
        }));
    },
});
frappe.ui.form.on("Salary Component Account", {
    company(frm, cdt, cdn) {
        frappe.model.set_value(cdt, cdn, "pph21_noncash_payable_account", null);
    },
});
