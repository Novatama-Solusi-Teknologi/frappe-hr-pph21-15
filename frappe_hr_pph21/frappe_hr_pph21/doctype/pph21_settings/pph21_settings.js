frappe.ui.form.on("PPh21 Settings", {
    setup(frm) {
        for (const [field, type, taxable] of [
            ["allowance_component", "Earning", 1],
            ["withholding_component", "Deduction", 0],
            ["refund_component", "Earning", 0],
        ]) {
            frm.set_query(field, () => ({filters: {type, is_tax_applicable: taxable,
                disabled: 0, statistical_component: 0, do_not_include_in_total: 0,
                do_not_include_in_accounts: 0, depends_on_payment_days: 0,
                variable_based_on_taxable_salary: 0, amount_based_on_formula: 0}}));
        }
        frm.set_query("noncash_offset_component", "component_mapping", () => ({
            filters: {type: "Deduction", disabled: 0, statistical_component: 0,
                do_not_include_in_total: 1, do_not_include_in_accounts: 0,
                depends_on_payment_days: 0, variable_based_on_taxable_salary: 0},
        }));
        frm.set_query("salary_component", "component_mapping", () => ({
            query: "frappe_hr_pph21.queries.salary_component_query",
        }));
    },
});
