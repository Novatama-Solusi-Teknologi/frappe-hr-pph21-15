frappe.ui.form.on("Bulk PPh21 Employee Tax Profile", {
	setup(frm) {
		frm.set_query("default_fiscal_year", () => ({ filters: { disabled: 0 } }));
		frm.set_query("fiscal_year", "employees", () => ({ filters: { disabled: 0 } }));
	},
	refresh(frm) {
		frm.set_intro(frm.doc.docstatus === 1
			? __("Batch telah diterapkan. Buka baris untuk melihat tautan profil. Aktivasi Employee dan saldo awal tetap diperiksa pada profil individual.")
			: __("Save hanya menyimpan draft. Submit membuat/memperbarui semua profil sekaligus; jika satu baris gagal, seluruh perubahan profil dibatalkan."));
	},
});

frappe.ui.form.on("Bulk PPh21 Employee Tax Profile Row", {
	employees_add(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, {
			fiscal_year: frm.doc.default_fiscal_year,
			method: frm.doc.default_method || "Gross Up",
		});
	},
	async employee(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const employee = row.employee;
		// Changing employees must not carry another person's identity or tax status.
		await frappe.model.set_value(cdt, cdn, {
			company: null, employee_name: null, ptkp_status: "", tax_id: "", tax_profile: null, result: null,
		});
		if (!employee) return;
		const { message } = await frappe.call({
			method: "frappe_hr_pph21.queries.employee_tax_defaults", args: { employee },
		});
		if (!locals[cdt]?.[cdn] || row.employee !== employee) return;
		await frappe.model.set_value(cdt, cdn, {
			company: message.company, employee_name: message.employee_name,
			ptkp_status: row.ptkp_status || message.ptkp_status || "",
		});
	},
});
