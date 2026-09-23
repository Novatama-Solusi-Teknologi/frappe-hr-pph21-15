frappe.ui.form.on("PPh21 Settings", {
	setup(frm) {
		for (const [field, root_type] of [["expense_account", "Expense"], ["tax_payable_account", "Liability"]]) {
			frm.set_query(field, () => ({
				filters: {
					company: frm.doc.company || "", root_type,
					is_group: 0, disabled: 0, account_currency: "IDR",
				},
			}));
		}
		frm.set_query("salary_component", "component_mapping", () => ({
			query: "frappe_hr_pph21.queries.salary_component_query",
		}));
	},
	company(frm) {
		// Clear previous selections immediately; server validation also checks ownership.
		return frm.set_value({ expense_account: null, tax_payable_account: null });
	},
});
