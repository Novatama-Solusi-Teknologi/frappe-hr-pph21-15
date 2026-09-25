frappe.ui.form.on("PPh21 Settings", {
    setup(frm) {
        frm.set_query("salary_component", "component_mapping", () => ({
            query: "frappe_hr_pph21.queries.salary_component_query",
        }));
    },
});
