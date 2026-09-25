"""Settings isolation, migration and native HRMS account lookup contracts."""
import ast
import copy
from datetime import date
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from test_bulk_profiles import Box, Doc, load

ROOT = Path(__file__).resolve().parents[1]
PAYROLL_SOURCE = ROOT.parent / '.build/contract_source/payroll_entry.py'


class Component(Doc):
    def set(self, key, value): self[key] = value
    def append(self, field, value): self.setdefault(field, []).append(Box(value))
    def insert(self, **kwargs):
        self.name = self.salary_component
        self.setdefault('accounts', [])
        STORE[self.name] = self
        return self
    def save(self, **kwargs): STORE[self.name] = self


class SettingsTest(unittest.TestCase):
    def setUp(self):
        global STORE
        STORE = {}
        self.posted = set()
        self.frappe = types.ModuleType('frappe')
        self.frappe.throw = lambda msg: (_ for _ in ()).throw(ValueError(msg))
        self.frappe.db = Box(exists=self.exists, get_value=self.get_value, sql=self.sql)
        self.frappe.get_doc = self.get_doc
        self.frappe.get_all = lambda *a, **kw: []
        custom = types.ModuleType('frappe.custom.doctype.custom_field.custom_field')
        custom.create_custom_fields = lambda *a, **kw: None
        document = types.ModuleType('frappe.model.document'); document.Document = Component
        utils = types.ModuleType('frappe.utils'); utils.getdate = lambda v: v
        self.patcher = patch.dict(sys.modules, {'frappe': self.frappe, 'frappe.utils': utils,
            'frappe.custom.doctype.custom_field.custom_field': custom, 'frappe.model.document': document})
        self.patcher.start(); self.addCleanup(self.patcher.stop)
        self.setup = load('settings_setup_test', 'frappe_hr_pph21/setup.py')
        p = patch.dict(sys.modules, {'frappe_hr_pph21.setup': self.setup}); p.start(); self.addCleanup(p.stop)
        self.controller = load('settings_controller_test', 'frappe_hr_pph21/frappe_hr_pph21/doctype/pph21_settings/pph21_settings.py').PPh21Settings
        self.helper = load('settings_helper_test', 'frappe_hr_pph21/settings.py')
        self.validation = load('settings_validation_test', 'frappe_hr_pph21/validation.py')
    def get_doc(self, doctype, name=None, **kwargs):
        if isinstance(doctype, dict): return Component(doctype)
        if doctype == 'Salary Component': return STORE[name]
        if doctype == 'Account':
            return Doc(company='PUP', is_group=0, root_type='Expense' if name.startswith('Expense') else 'Liability', account_currency='IDR')
        raise AssertionError(doctype)
    def get_value(self, dt, filters, field, **kwargs):
        if dt == 'Company': return 'IDR'
        if dt == 'Salary Component Account':
            assert field == 'account'  # actual HRMS v15 field, not default_account
            return next(r.account for r in STORE[filters['parent']].accounts if r.company == filters['company'])
        raise AssertionError(dt)
    def exists(self, dt, filters):
        if dt == 'Salary Component': return filters in STORE
        if dt == 'Salary Slip': return False
        raise AssertionError(dt)
    def sql(self, query, args):
        if 'SELECT ss.name' in query:
            return [('SLIP',)] if args[0] in self.posted else []
        if 'FOR UPDATE' in query: return []
        return [('SLIP',)] if args[0] in self.posted else []
    def settings(self, name='PPH21-SET-00001', expense='Expense A', payable='Liability A'):
        s = self.controller(name=name, settings_name='PUP - '+name, company='PUP', enabled=1,
                            expense_account=expense, tax_payable_account=payable,
                            component_mapping=[], rounding='Floor IDR')
        s.validate(); s.on_update()
        return s
    def test_additional_salary_checks_actual_submitted_work_period(self):
        original_get=self.frappe.db.get_value
        self.frappe.db.get_value=lambda dt, filters, field, **kw: 1 if dt=='Employee' else original_get(dt,filters,field,**kw)
        checked=[]
        def exists(dt, filters):
            if dt!='Salary Slip': return False
            checked.append(filters)
            self.assertEqual(filters['company'],'PUP')
            self.assertEqual(filters['pph21_tax_profile'],['is','set'])
            return date(2026,8,26) <= filters['start_date'][1] and date(2026,9,25) >= filters['end_date'][1]
        self.frappe.db.exists=exists
        for day in (date(2026,8,26),date(2026,8,30),date(2026,9,25)):
            with self.assertRaisesRegex(ValueError,'submitted'):
                self.validation.validate_additional_salary(Doc(salary_component='Bonus',employee='EMP',company='PUP',payroll_date=day))
        self.validation.validate_additional_salary(Doc(salary_component='Bonus',employee='EMP',company='PUP',payroll_date=date(2026,9,26)))
        with self.assertRaisesRegex(ValueError,'submitted'):
            self.validation.validate_additional_salary(Doc(salary_component='Bonus',employee='EMP',company='PUP',is_recurring=1,
                from_date=date(2026,8,1),to_date=date(2026,8,31)))
        self.assertEqual(len(checked),5)

    def test_two_settings_same_company_get_distinct_components_and_accounts(self):
        a = self.settings(); b = self.settings('PPH21-SET-00002','Expense B','Liability B')
        self.assertEqual(len(STORE),6)
        for s in (a,b):
            for base,name in self.setup.settings_components(s).items():
                c = self.setup.validate_component(name)
                expected = s.expense_account if base == self.setup.ALLOWANCE else s.tax_payable_account
                self.assertEqual(c.accounts[0].account,expected)
        self.assertNotEqual(a.allowance_component,b.allowance_component)
        a.on_update(); self.assertEqual(len(STORE),6)
    @unittest.skipUnless(PAYROLL_SOURCE.exists(),'Requires HRMS v15 Payroll Entry source')
    def test_native_payroll_entry_routes_mixed_settings_components_to_separate_accounts(self):
        a=self.settings(); b=self.settings('PPH21-SET-00002','Expense B','Liability B')
        tree=ast.parse(PAYROLL_SOURCE.read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='PayrollEntry')
        methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('get_salary_component_account','get_account')]
        namespace={'frappe':self.frappe}
        exec(compile(ast.Module(body=methods,type_ignores=[]),str(PAYROLL_SOURCE),'exec'),namespace)
        payroll=Box(company='PUP');lookup=namespace['get_salary_component_account']
        self.assertEqual([lookup(payroll,s.allowance_component) for s in (a,b)],['Expense A','Expense B'])
        self.assertEqual([lookup(payroll,s.withholding_component) for s in (a,b)],['Liability A','Liability B'])
        self.assertEqual(lookup(payroll,b.refund_component),'Liability B')
        payroll.get_salary_component_account=lambda component: lookup(payroll,component)
        accounts=namespace['get_account'](payroll,{(a.allowance_component,'Main'):230179,
            (b.allowance_component,'Main'):121827})
        self.assertEqual(accounts,{('Expense A','Main'):230179,('Expense B','Main'):121827})
    def test_generated_components_cannot_enter_structure_or_additional_salary(self):
        s=self.settings()
        for name in self.setup.settings_components(s).values():
            with self.assertRaisesRegex(ValueError,'otomatis'):
                self.validation.validate_salary_structure(Doc(earnings=[Box(salary_component=name)]))
            with self.assertRaisesRegex(ValueError,'Additional Salary'):
                self.validation.validate_additional_salary(Doc(salary_component=name))
    def test_company_immutable_and_client_component_links_ignored(self):
        s=self.settings(); original=s.allowance_component
        s._old=Doc(copy.deepcopy(s)); s.allowance_component='Hijacked';s.validate()
        self.assertEqual(s.allowance_component,original)
        s.company='Other'
        with self.assertRaisesRegex(ValueError,'Company'): s.validate()
    def test_posted_settings_lock_accounts_and_rounding_but_other_settings_remain_editable(self):
        a=self.settings(); b=self.settings('PPH21-SET-00002','Expense B','Liability B')
        self.posted.add(a.allowance_component)
        a._old=Doc(copy.deepcopy(a));a.expense_account='Expense Changed'
        with self.assertRaisesRegex(ValueError,'submitted'): a.validate()
        a.expense_account=a._old.expense_account;a.rounding='Half Up IDR'
        with self.assertRaisesRegex(ValueError,'submitted'): a.validate()
        b._old=Doc(copy.deepcopy(b));b.expense_account='Expense Changed';b.validate();b.on_update()
        self.assertEqual(STORE[b.allowance_component].accounts[0].account,'Expense Changed')
    def test_posted_component_mapping_cannot_be_changed_manually(self):
        s=self.settings();c=STORE[s.allowance_component];self.posted.add(c.name)
        c._old=Doc(copy.deepcopy(c));c.accounts[0].account='Expense Wrong'
        with self.assertRaisesRegex(ValueError,'dikunci'): self.validation.validate_generated_component(c)
    def test_zero_tax_submitted_slip_also_locks_settings_rounding(self):
        s=self.settings();self.posted.add(s.name)
        s._old=Doc(copy.deepcopy(s));s.rounding='Half Up IDR'
        with self.assertRaisesRegex(ValueError,'submitted'): s.validate()
    def test_backfill_is_idempotent_preserves_legacy_and_skips_ambiguous_company(self):
        records={
            'PPh21 Settings':[Box(name='PUP',company='PUP',settings_name=None),
                               Box(name='A1',company='Other',settings_name='A1'),Box(name='A2',company='Other',settings_name='A2')],
            'PPh21 Employee Tax Profile':[Box(name='EMP-2026',company='PUP',opening_tax=123),
                                         Box(name='OTHER',company='Other'),Box(name='MISSING',company='None')],
            'Bulk PPh21 Employee Tax Profile Row':[Box(name='ROW',company='PUP')],
        }
        changes=[]
        self.frappe.get_all=lambda dt,**kw: records[dt]
        def set_value(dt,name,field,value=None,**kwargs):
            self.assertFalse(kwargs['update_modified'])
            doc=next(d for d in records[dt] if d.name==name)
            doc.update(field if isinstance(field,dict) else {field:value});changes.append(name)
        self.frappe.db.set_value=set_value
        self.helper.migrate_settings_links();self.helper.migrate_settings_links()
        self.assertEqual(changes,['PUP','EMP-2026','ROW'])
        self.assertEqual(records['PPh21 Settings'][0].allowance_component,self.setup.ALLOWANCE)
        profile=records['PPh21 Employee Tax Profile'][0]
        self.assertEqual((profile.pph21_settings,profile.opening_tax),('PUP',123))
        self.assertFalse(records['PPh21 Employee Tax Profile'][1].pph21_settings)
    def test_missing_legacy_accounts_can_be_configured_without_replacing_components(self):
        self.setup.create_components()
        s=self.controller(name='PUP',settings_name='PUP - Standar',company='PUP',expense_account='Expense Legacy',tax_payable_account='Liability Legacy',rounding='Floor IDR',component_mapping=[])
        for base,field in self.setup.COMPONENT_FIELDS.items(): s[field]=base
        s._old=Doc(copy.deepcopy(s));self.posted.add(self.setup.ALLOWANCE)
        s.validate();s.on_update()
        self.assertEqual(len(STORE),3)
        self.assertEqual(STORE[self.setup.ALLOWANCE].accounts[0].account,'Expense Legacy')

if __name__ == '__main__': unittest.main()
