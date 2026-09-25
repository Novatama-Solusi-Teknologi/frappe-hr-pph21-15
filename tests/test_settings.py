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
        if dt == 'PPh21 Component Tax Mapping': return True
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
        for base, name in self.setup.settings_components(s).items():
            STORE[name].append('accounts', dict(company='PUP', account=expense if base==self.setup.ALLOWANCE else payable))
        return s
    def test_worksheet_custom_field_hides_json_without_removing_it(self):
        captured={}
        self.setup.create_custom_fields=lambda fields,**kwargs: captured.update(fields)
        self.setup.sync_custom_fields()
        fields={f['fieldname']:f for f in captured['Salary Slip']}
        self.assertEqual(fields['pph21_tax_worksheet']['fieldtype'],'HTML')
        self.assertEqual(fields['pph21_tax_worksheet']['insert_after'],'pph21_snapshot_section')
        self.assertEqual(fields['pph21_tax_snapshot']['fieldtype'],'Code')
        self.assertEqual(fields['pph21_tax_snapshot']['hidden'],1)
        self.assertEqual(fields['pph21_tax_snapshot']['read_only'],1)

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

    def noncash_settings(self, name='PPH21-SET-00001', treatment='Taxable Noncash'):
        s=self.settings(name)
        STORE['BPJS']=Component(name='BPJS',type='Earning',salary_component_abbr='BPJS',
            do_not_include_in_total=1,do_not_include_in_accounts=1,statistical_component=0,
            variable_based_on_taxable_salary=0,accounts=[Box(company='PUP',account='Expense BPJS')])
        s.component_mapping=[Box(salary_component='BPJS',treatment=treatment,noncash_payable_account='Liability BPJS')]
        s.validate();s.on_update()
        STORE[s.component_mapping[0].noncash_offset_component].append('accounts',dict(company='PUP',account='Liability BPJS'))
        return s

    def test_noncash_pair_is_created_once_with_liability_account_and_no_cash_impact(self):
        s=self.noncash_settings()
        name=s.component_mapping[0].noncash_offset_component
        pair=self.setup.validate_component(name)
        self.assertEqual((pair.type,pair.do_not_include_in_total,pair.do_not_include_in_accounts),('Deduction',1,0))
        self.assertEqual(pair.accounts[0].account,'Liability BPJS')
        self.assertEqual(STORE['BPJS'].do_not_include_in_accounts,1)  # master not silently rewritten
        count=len(STORE);s.on_update();self.assertEqual(len(STORE),count)
        for validator,doc in [(self.validation.validate_salary_structure,Doc(earnings=[],deductions=[Box(salary_component=name)])),
                              (self.validation.validate_additional_salary,Doc(salary_component=name))]:
            with self.assertRaises(ValueError): validator(doc)

    def test_nontaxable_employer_contribution_also_gets_pair(self):
        s=self.noncash_settings(treatment='Non Taxable')
        self.assertTrue(s.component_mapping[0].noncash_offset_component)
        s.component_mapping[0].noncash_payable_account=None
        s.validate();s.on_update()  # obsolete account field has no effect
        self.assertEqual(STORE[s.component_mapping[0].noncash_offset_component].accounts[0].account,'Liability BPJS')

    def test_noncash_accounts_validate_root_company_and_posted_mapping_lock(self):
        s=self.noncash_settings();m=s.component_mapping[0]
        pair=STORE[m.noncash_offset_component]
        pair.accounts[0].account='Expense Wrong'
        with self.assertRaisesRegex(ValueError,'Liability'):
            self.setup.component_account(pair,'PUP','Liability')
        pair.accounts[0].account='Wrong Co'
        get_doc=self.frappe.get_doc
        self.frappe.get_doc=lambda dt,name=None,**kw: Doc(company='Other',root_type='Liability',is_group=0,account_currency='IDR') if name=='Wrong Co' else get_doc(dt,name,**kw)
        with self.assertRaisesRegex(ValueError,'Company'):
            self.setup.component_account(pair,'PUP','Liability')
        s._old=Doc(copy.deepcopy(s));self.posted.add(pair.name)
        m.treatment='Non Taxable'
        with self.assertRaisesRegex(ValueError,'submitted'): s.validate()
        s.component_mapping=[]
        with self.assertRaisesRegex(ValueError,'submitted'): s.validate()

    def test_noncash_source_account_changes_are_locked_after_submission(self):
        self.noncash_settings();source=STORE['BPJS'];source._old=Doc(copy.deepcopy(source))
        self.posted.add('BPJS');source.accounts[0].account='Expense Changed'
        with self.assertRaisesRegex(ValueError,'dikunci'): self.validation.validate_generated_component(source)

    def test_each_settings_gets_a_distinct_noncash_pair(self):
        a=self.noncash_settings();b=self.noncash_settings('PPH21-SET-00002')
        self.assertNotEqual(a.component_mapping[0].noncash_offset_component,b.component_mapping[0].noncash_offset_component)

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
    def test_settings_never_overwrites_master_accounts_and_rounding_stays_locked(self):
        a=self.settings();b=self.settings('PPH21-SET-00002','Expense B','Liability B')
        self.posted.add(a.allowance_component)
        a._old=Doc(copy.deepcopy(a));a.expense_account='Expense Obsolete'
        a.validate();a.on_update()
        self.assertEqual(STORE[a.allowance_component].accounts[0].account,'Expense A')
        a.rounding='Half Up IDR'
        with self.assertRaisesRegex(ValueError,'submitted'): a.validate()
        STORE[b.allowance_component].accounts[0].account='Expense Changed'
        b.validate();b.on_update()
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
        self.assertEqual(STORE[self.setup.ALLOWANCE].accounts,[])
        STORE[self.setup.ALLOWANCE].append('accounts',dict(company='PUP',account='Expense Legacy'))
        s.on_update()
        self.assertEqual(STORE[self.setup.ALLOWANCE].accounts[0].account,'Expense Legacy')

    def test_new_settings_and_noncash_pair_can_save_before_accounts_are_configured(self):
        s=self.controller(name='NEW',settings_name='New',company='PUP',rounding='Floor IDR',component_mapping=[])
        s.validate();s.on_update()
        self.assertEqual(STORE[s.allowance_component].accounts,[])
        s=self.noncash_settings()
        pair=STORE[s.component_mapping[0].noncash_offset_component]
        pair.accounts=[]
        s.on_update()
        self.assertEqual(pair.accounts,[])
        with self.assertRaisesRegex(ValueError,'tepat satu akun'):
            self.setup.component_account(pair,'PUP','Liability')

    def test_duplicate_company_account_is_rejected_but_multiple_companies_are_allowed(self):
        s=self.settings();c=STORE[s.allowance_component]
        c.append('accounts',dict(company='Other',account='Expense Other'))
        self.assertEqual(self.setup.component_account(c,'PUP','Expense'),'Expense A')
        c.append('accounts',dict(company='PUP',account='Expense Duplicate'))
        with self.assertRaisesRegex(ValueError,'tepat satu akun'):
            self.setup.component_account(c,'PUP','Expense')
        with self.assertRaisesRegex(ValueError,'satu baris'):
            self.validation.validate_generated_component(c)

    def migration_fixture(self, settings):
        original=self.frappe.get_doc
        self.frappe.get_all=lambda dt,**kw: [Box(name=s.name) for s in settings]
        self.frappe.get_doc=lambda dt,name=None,**kw: next(s for s in settings if s.name==name) if dt=='PPh21 Settings' else original(dt,name,**kw)
        changes=[]
        def set_value(dt,name,field,value,**kwargs):
            self.assertEqual(dt,'PPh21 Component Tax Mapping')
            self.assertFalse(kwargs['update_modified'])
            changes.append((name,field,value))
            for s in settings:
                for row in s.component_mapping:
                    if row.name==name: row[field]=value
        self.frappe.db.set_value=set_value
        self.frappe.clear_document_cache=lambda *a: None
        return changes

    def test_upgrade_backfills_missing_noncash_pair_without_saving_settings_or_choosing_account(self):
        s=self.noncash_settings();row=s.component_mapping[0];row.name='LEGACY-ROW'
        expected=row.noncash_offset_component
        del STORE[expected];row.noncash_offset_component=None
        self.posted.add(s.name)  # existing submitted history must not block metadata backfill
        changes=self.migration_fixture([s])
        self.setup.sync_noncash_components()
        self.assertEqual(row.noncash_offset_component,expected)
        self.assertEqual(STORE[expected].accounts,[])
        self.assertEqual(STORE['BPJS'].accounts[0].account,'Expense BPJS')
        self.assertEqual(changes,[('LEGACY-ROW','noncash_offset_component',expected)])
        STORE[expected].append('accounts',dict(company='PUP',account='Liability User'))
        count=len(STORE);self.setup.sync_noncash_components()
        self.assertEqual(len(STORE),count);self.assertEqual(len(changes),1)
        self.assertEqual(STORE[expected].accounts[0].account,'Liability User')

    def test_upgrade_reconnects_existing_pair_and_preserves_its_accounts(self):
        s=self.noncash_settings(treatment='Non Taxable');row=s.component_mapping[0]
        row.name='NON-TAXABLE';expected=row.noncash_offset_component;row.noncash_offset_component=''
        self.migration_fixture([s]);self.setup.sync_noncash_components()
        self.assertEqual(row.noncash_offset_component,expected)
        self.assertEqual(STORE[expected].accounts[0].account,'Liability BPJS')

    def test_upgrade_skips_cash_and_conflicting_pair_links(self):
        s=self.noncash_settings();row=s.component_mapping[0];row.name='EXISTING'
        row.noncash_offset_component='Another pair'
        STORE['Cash']=Component(name='Cash',type='Earning',do_not_include_in_total=0)
        s.component_mapping.append(Box(name='CASH',salary_component='Cash',treatment='Taxable Cash'))
        changes=self.migration_fixture([s]);count=len(STORE)
        self.setup.sync_noncash_components()
        self.assertEqual(row.noncash_offset_component,'Another pair')
        self.assertFalse(changes);self.assertEqual(len(STORE),count)

    def test_after_migrate_runs_backfill_after_settings_migration(self):
        calls=[]
        fiscal=types.ModuleType('frappe_hr_pph21.fiscal_year')
        fiscal.backfill_fiscal_year_links=lambda: calls.append('fiscal')
        settings=types.ModuleType('frappe_hr_pph21.settings')
        settings.migrate_settings_links=lambda: calls.append('settings')
        workspace=types.ModuleType('frappe_hr_pph21.workspace')
        workspace.sync_navigation=lambda: calls.append('workspace')
        names=('check_versions','sync_custom_fields','create_components','sync_mapping_codes','sync_noncash_components')
        with patch.dict(sys.modules, {'frappe_hr_pph21.fiscal_year':fiscal,
                'frappe_hr_pph21.settings':settings,'frappe_hr_pph21.workspace':workspace}):
            with patch.multiple(self.setup, **{n:(lambda name=n: calls.append(name)) for n in names}):
                self.setup.after_migrate()
        self.assertEqual(calls,['check_versions','sync_custom_fields','create_components','sync_mapping_codes',
                               'fiscal','settings','sync_noncash_components','workspace'])

if __name__ == '__main__': unittest.main()
