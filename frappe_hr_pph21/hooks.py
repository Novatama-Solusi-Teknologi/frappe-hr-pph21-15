app_name = "frappe_hr_pph21"
app_title = "Frappe HR PPh21"
app_publisher = "PT PUP"
app_description = "PPh 21 TER, gross-up, and annual reconciliation for Indonesia"
app_email = ""
app_license = "MIT"
required_apps = ["erpnext", "hrms"]

before_install = "frappe_hr_pph21.setup.check_versions"
after_install = "frappe_hr_pph21.setup.after_install"
after_migrate = "frappe_hr_pph21.setup.after_migrate"

override_doctype_class = {
    "Salary Slip": "frappe_hr_pph21.overrides.salary_slip.PPh21SalarySlip",
}

doctype_js = {"Salary Slip": "public/js/salary_slip.js"}

doc_events = {
    "Additional Salary": {"validate": "frappe_hr_pph21.validation.validate_additional_salary"},
    "Salary Structure": {"validate": "frappe_hr_pph21.validation.validate_salary_structure"},
}
