"""Run only on a Frappe testing site after installing this app."""
import frappe
from frappe.model.base_document import get_controller
from frappe.tests.utils import FrappeTestCase

from frappe_hr_pph21.overrides.salary_slip import PPh21SalarySlip
from frappe_hr_pph21.setup import COMPONENTS, create_components, validate_component


class TestPPh21Installation(FrappeTestCase):
    def test_schema_and_controller(self):
        for name in ('PPh21 Settings', 'PPh21 Employee Tax Profile', 'PPh21 Component Tax Mapping'):
            self.assertTrue(frappe.db.exists('DocType', name))
        self.assertTrue(frappe.get_meta('Employee').has_field('pph21_enabled'))
        meta = frappe.get_meta('Salary Slip')
        self.assertTrue(meta.has_field('pph21_tax_snapshot'))
        self.assertTrue(meta.get_field('pph21_tax_key').unique)
        self.assertTrue(issubclass(get_controller('Salary Slip'), PPh21SalarySlip))

    def test_components_and_idempotent_seed(self):
        original = {name: frappe.get_doc('Salary Component', name).as_dict() for name in COMPONENTS}
        create_components()
        for name in COMPONENTS:
            doc = validate_component(name)
            self.assertEqual(doc.modified, original[name]['modified'])

    def test_reports_and_workspace(self):
        self.assertTrue(frappe.db.exists('Workspace', 'Frappe HR PPh21'))
        for name in ('PPh21 Register', 'PPh21 TER Reference'):
            self.assertTrue(frappe.db.exists('Report', name))
