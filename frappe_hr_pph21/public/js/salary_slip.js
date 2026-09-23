frappe.ui.form.on("Salary Slip", {
    refresh(frm) {
        if (!frm.doc.pph21_tax_snapshot) return;
        frm.set_df_property("income_tax_calculation_breakup_section", "hidden", 1);
        frm.add_custom_button(__("Kertas Kerja PPh 21"), () => {
            const text = frappe.utils.escape_html(frm.doc.pph21_tax_snapshot);
            const dialog = new frappe.ui.Dialog({
                title: __("Kertas Kerja PPh 21"), size: "large",
                fields: [{fieldtype: "HTML", fieldname: "worksheet"}],
            });
            dialog.fields_dict.worksheet.$wrapper.html(`<pre style="white-space:pre-wrap">${text}</pre>`);
            dialog.show();
        });
    },
});
