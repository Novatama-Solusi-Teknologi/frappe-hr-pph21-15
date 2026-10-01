"""Run only on a Frappe testing site after installing this app."""
import frappe
from frappe.model.base_document import get_controller
from frappe.tests.utils import FrappeTestCase

from frappe_hr_pph21.overrides.salary_slip import PPh21SalarySlip
from frappe_hr_pph21.setup import after_install


class TestPPh21Installation(FrappeTestCase):
    def test_schema_and_controller(self):
        for name in ('PPh21 Settings', 'PPh21 Employee Tax Profile', 'PPh21 Component Tax Mapping',
                     'Bulk PPh21 Employee Tax Profile', 'Bulk PPh21 Employee Tax Profile Row'):
            self.assertTrue(frappe.db.exists('DocType', name))
        self.assertTrue(frappe.get_meta('Employee').has_field('pph21_enabled'))
        meta = frappe.get_meta('Salary Slip')
        self.assertTrue(meta.has_field('pph21_tax_snapshot'))
        self.assertTrue(meta.get_field('pph21_tax_snapshot').hidden)
        self.assertEqual(meta.get_field('pph21_tax_worksheet').fieldtype, 'HTML')
        self.assertTrue(meta.get_field('pph21_tax_payment_date').read_only)
        self.assertTrue(meta.get_field('pph21_tax_key').unique)
        self.assertTrue(meta.has_field('pph21_allowance_column'))
        self.assertTrue(frappe.get_meta('Bulk PPh21 Employee Tax Profile').is_submittable)
        self.assertTrue(frappe.get_meta('PPh21 Component Tax Mapping').has_field('component_abbr'))
        self.assertTrue(issubclass(get_controller('Salary Slip'), PPh21SalarySlip))

    def test_install_does_not_create_components(self):
        original = set(frappe.get_all('Salary Component', pluck='name'))
        after_install()
        self.assertEqual(set(frappe.get_all('Salary Component', pluck='name')), original)
        for field in ('allowance_component', 'withholding_component', 'refund_component'):
            spec = frappe.get_meta('PPh21 Settings').get_field(field)
            self.assertFalse(spec.read_only)
            self.assertTrue(spec.reqd)

    def test_reports_and_workspace(self):
        self.assertTrue(frappe.db.exists('Workspace', 'PPh 21'))
        self.assertEqual(frappe.db.get_value('Workspace', 'PPh 21', 'parent_page'), 'HR')
        for name in ('PPh21 Register', 'PPh21 TER Reference'):
            self.assertTrue(frappe.db.exists('Report', name))
