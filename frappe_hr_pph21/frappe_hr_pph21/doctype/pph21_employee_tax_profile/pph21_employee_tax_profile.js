frappe.ui.form.on("PPh21 Employee Tax Profile", {
	async employee(frm) {
		const employee = frm.doc.employee;
		await frm.set_value({ company: null, employee_name: null, tax_id: "", ptkp_status: "", ter_category: "" });
		if (!employee) {
			return;
		}
		const { message } = await frappe.call({
			method: "frappe_hr_pph21.queries.employee_tax_defaults", args: { employee },
		});
		if (frm.doc.employee !== employee) return;
		await frm.set_value({ company: message.company, employee_name: message.employee_name,
			ptkp_status: frm.doc.ptkp_status || message.ptkp_status || "" });
	},
	ptkp_status(frm) {
		const categories = { "TK/0": "A", "TK/1": "A", "K/0": "A", "TK/2": "B", "TK/3": "B", "K/1": "B", "K/2": "B", "K/3": "C" };
		return frm.set_value("ter_category", categories[frm.doc.ptkp_status] || "");
	},
});
