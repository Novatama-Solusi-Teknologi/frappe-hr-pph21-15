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
        self.saved_settings = []
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
        if dt == 'PPh21 Settings':
            return any(all(s.get(k)==v for k,v in filters.items()) for s in self.saved_settings)
        if dt == 'PPh21 Component Tax Mapping':
            rows=[r for s in self.saved_settings for r in s.component_mapping]
            if 'salary_component' in filters:
                return any(r.salary_component==filters['salary_component'] and ('noncash_offset_component' not in filters or r.get('noncash_offset_component')) for r in rows)
            return any(r.get('noncash_offset_component')==filters.get('noncash_offset_component') for r in rows)
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
        for role, field in self.setup.COMPONENT_FIELDS.items():
            # Site/user masters, not app-generated names.
            name = {'allowance_component':'Tunjangan Pajak', 'withholding_component':'Potongan Pajak',
                    'refund_component':'Refund Pajak'}[field] + ' ' + s.name
            self.make_tax_component(name, role, expense if role==self.setup.ALLOWANCE else payable)
            s[field]=name
        s.validate()
        self.saved_settings.append(s)
        return s
    def make_tax_component(self, name, role, account):
        kind, _, taxable = self.setup.COMPONENTS[role]
        STORE[name]=Component(name=name,type=kind,salary_component_abbr='C'+str(len(STORE)),
            is_tax_applicable=taxable, accounts=[Box(company='PUP',account=account)])
        return STORE[name]

    def test_many_settings_share_existing_tax_masters_without_modifying_them(self):
        a=self.settings()
        before=copy.deepcopy(STORE)
        b=self.controller(name='B',settings_name='PUP Produksi',company='PUP',enabled=1,
            rounding='Floor IDR',component_mapping=[],**{f:a[f] for f in self.setup.COMPONENT_FIELDS.values()})
        b.validate();self.saved_settings.append(b)
        self.assertEqual(STORE,before)
        self.assertEqual(self.setup.settings_components(a),self.setup.settings_components(b))
        # Submitted use by A must not lock B's otherwise independent rounding.
        self.posted.add(a.name);b._old=Doc(copy.deepcopy(b));b.rounding='Half Up IDR';b.validate()

    def test_tax_component_selection_rejects_duplicate_roles_and_cross_settings_role_conflict(self):
        s=self.settings();original=s.refund_component;s.refund_component=s.allowance_component
        with self.assertRaisesRegex(ValueError,'tiga komponen berbeda'): s.validate()
        s.refund_component=original
        other=self.controller(name='B',settings_name='B',company='PUP',rounding='Floor IDR',component_mapping=[],
            allowance_component=s.refund_component,refund_component=s.allowance_component,
            withholding_component=s.withholding_component)
        with self.assertRaisesRegex(ValueError,'peran pajak lain'): other.validate()

    def test_manual_tax_master_flags_formula_and_account_validation(self):
        s=self.settings();c=STORE[s.allowance_component]
        for field,value in [('type','Deduction'),('is_tax_applicable',0),('depends_on_payment_days',1),
                ('statistical_component',1),('do_not_include_in_total',1),('do_not_include_in_accounts',1),
                ('variable_based_on_taxable_salary',1),('amount_based_on_formula',1),('disabled',1),
                ('amount',500),('formula','base*.01'),('condition','1'),('salary_component_abbr','')]:
            old=c.get(field);c[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError): s.validate()
            c[field]=old
        c.accounts[0].account='Liability Wrong'
        with self.assertRaisesRegex(ValueError,'Expense'): s.validate()

    def test_tax_components_cannot_overlap_sources_or_noncash_pairs(self):
        s=self.settings()
        s.component_mapping=[Box(salary_component=s.allowance_component,treatment='Taxable Cash')]
        with self.assertRaisesRegex(ValueError,'sumber mapping'): s.validate()
        s.component_mapping=[Box(salary_component='BPJS',treatment='Taxable Noncash',noncash_offset_component=s.withholding_component)]
        with self.assertRaisesRegex(ValueError,'pasangan noncash'): s.validate()
        s.component_mapping=[]
        other=self.noncash_settings('B')
        name=other.component_mapping[0].noncash_offset_component
        with self.assertRaisesRegex(ValueError,'pasangan noncash'):
            self.setup.validate_component(name,role=self.setup.WITHHOLDING)
        with self.assertRaisesRegex(ValueError,'Komponen pajak'):
            self.setup.validate_noncash_component(s.withholding_component)

    def test_install_and_migrate_have_no_salary_component_creator(self):
        before=copy.deepcopy(STORE);self.setup.after_install();self.assertEqual(STORE,before)
        self.assertFalse(hasattr(self.setup,'create_components'))
        self.assertFalse(hasattr(self.controller,'on_update'))


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
        pair='Utang BPJS Perusahaan'
        if pair not in STORE:
            STORE[pair]=Component(name=pair,type='Deduction',salary_component_abbr='UBPJS',do_not_include_in_total=1,
                do_not_include_in_accounts=0,accounts=[Box(company='PUP',account='Liability BPJS')])
        s.component_mapping=[Box(salary_component='BPJS',treatment=treatment,noncash_offset_component=pair)]
        s.validate();s.validate()
        return s

    def test_selected_noncash_pair_is_preserved_with_liability_account_and_no_cash_impact(self):
        s=self.noncash_settings()
        name=s.component_mapping[0].noncash_offset_component
        pair=self.setup.validate_noncash_component(name)
        self.assertEqual((pair.type,pair.do_not_include_in_total,pair.do_not_include_in_accounts),('Deduction',1,0))
        self.assertEqual(pair.accounts[0].account,'Liability BPJS')
        self.assertEqual(STORE['BPJS'].do_not_include_in_accounts,1)  # master not silently rewritten
        count=len(STORE);s.validate();self.assertEqual(len(STORE),count)
        for validator,doc in [(self.validation.validate_salary_structure,Doc(earnings=[],deductions=[Box(salary_component=name)])),
                              (self.validation.validate_additional_salary,Doc(salary_component=name))]:
            with self.assertRaises(ValueError): validator(doc)

    def test_nontaxable_employer_contribution_also_gets_pair(self):
        s=self.noncash_settings(treatment='Non Taxable')
        self.assertTrue(s.component_mapping[0].noncash_offset_component)
        s.component_mapping[0].noncash_payable_account=None
        s.validate();s.validate()  # obsolete account field has no effect
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
        s._old=Doc(copy.deepcopy(s));self.posted.add(s.name)
        m.treatment='Non Taxable'
        with self.assertRaisesRegex(ValueError,'submitted'): s.validate()
        s.component_mapping=[]
        with self.assertRaisesRegex(ValueError,'submitted'): s.validate()

    def test_noncash_source_account_changes_are_locked_after_submission(self):
        self.noncash_settings();source=STORE['BPJS'];source._old=Doc(copy.deepcopy(source))
        self.posted.add('BPJS');source.accounts[0].account='Expense Changed'
        with self.assertRaisesRegex(ValueError,'dikunci'): self.validation.validate_generated_component(source)

    def test_settings_can_share_one_selected_noncash_pair(self):
        a=self.noncash_settings();b=self.noncash_settings('PPH21-SET-00002')
        self.assertEqual(a.component_mapping[0].noncash_offset_component,b.component_mapping[0].noncash_offset_component)

    def test_two_settings_can_select_different_existing_components_and_accounts(self):
        a = self.settings(); b = self.settings('PPH21-SET-00002','Expense B','Liability B')
        self.assertEqual(len(STORE),6)
        for s in (a,b):
            for base,name in self.setup.settings_components(s).items():
                c = self.setup.validate_component(name, role=base)
                expected = s.expense_account if base == self.setup.ALLOWANCE else s.tax_payable_account
                self.assertEqual(c.accounts[0].account,expected)
        self.assertNotEqual(a.allowance_component,b.allowance_component)
        a.validate(); self.assertEqual(len(STORE),6)
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
            with self.assertRaisesRegex(ValueError,'diisi oleh app'):
                self.validation.validate_salary_structure(Doc(earnings=[Box(salary_component=name)]))
            with self.assertRaisesRegex(ValueError,'Additional Salary'):
                self.validation.validate_additional_salary(Doc(salary_component=name))
    def test_company_immutable_and_component_selection_can_change_before_submission(self):
        s=self.settings(); s._old=Doc(copy.deepcopy(s))
        self.make_tax_component('Tunjangan Bersama',self.setup.ALLOWANCE,'Expense Shared')
        s.allowance_component='Tunjangan Bersama';s.validate()
        self.assertEqual(s.allowance_component,'Tunjangan Bersama')
        self.posted.add(s.name);s._old=Doc(copy.deepcopy(s))
        s.allowance_component='Tunjangan Pajak PPH21-SET-00001'
        with self.assertRaisesRegex(ValueError,'submitted'): s.validate()
        s.company='Other'
        with self.assertRaisesRegex(ValueError,'Company'): s.validate()
    def test_settings_never_overwrites_master_accounts_and_rounding_stays_locked(self):
        a=self.settings();b=self.settings('PPH21-SET-00002','Expense B','Liability B')
        self.posted.add(a.name)
        a._old=Doc(copy.deepcopy(a));a.expense_account='Expense Obsolete'
        a.validate();a.validate()
        self.assertEqual(STORE[a.allowance_component].accounts[0].account,'Expense A')
        a.rounding='Half Up IDR'
        with self.assertRaisesRegex(ValueError,'submitted'): a.validate()
        STORE[b.allowance_component].accounts[0].account='Expense Changed'
        b.validate();b.validate()
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
    def test_legacy_selected_components_are_preserved_without_creating_more(self):
        s=self.settings()
        for role,field in self.setup.COMPONENT_FIELDS.items():
            self.make_tax_component(role,role,'Expense Legacy' if role==self.setup.ALLOWANCE else 'Liability Legacy')
            s[field]=role
        s._old=Doc(copy.deepcopy(s));self.posted.add(s.name)
        before=copy.deepcopy(STORE);s.validate()
        self.assertEqual(STORE,before)
        self.assertEqual(s.allowance_component,self.setup.ALLOWANCE)

    def test_new_settings_requires_selected_masters_and_accounts_without_creating_any(self):
        s=self.controller(name='NEW',settings_name='New',company='PUP',rounding='Floor IDR',component_mapping=[])
        with self.assertRaisesRegex(ValueError,'Pilih komponen'): s.validate()
        self.assertEqual(STORE,{})
        s=self.settings();STORE[s.allowance_component].accounts=[]
        with self.assertRaisesRegex(ValueError,'tepat satu akun'): s.validate()
        self.assertEqual(STORE[s.allowance_component].accounts,[])

    def test_duplicate_company_account_is_rejected_but_multiple_companies_are_allowed(self):
        s=self.settings();c=STORE[s.allowance_component]
        c.append('accounts',dict(company='Other',account='Expense Other'))
        self.assertEqual(self.setup.component_account(c,'PUP','Expense'),'Expense A')
        c.append('accounts',dict(company='PUP',account='Expense Duplicate'))
        with self.assertRaisesRegex(ValueError,'tepat satu akun'):
            self.setup.component_account(c,'PUP','Expense')
        with self.assertRaisesRegex(ValueError,'satu baris'):
            self.validation.validate_generated_component(c)

    def test_manual_pair_is_required_and_no_pair_is_created_during_save(self):
        s=self.noncash_settings();s.component_mapping[0].noncash_offset_component=None
        before=set(STORE)
        with self.assertRaisesRegex(ValueError,'pilih Komponen Pasangan'): s.validate()
        self.assertEqual(set(STORE),before)
        self.assertFalse(any(n.startswith(self.setup.NONCASH_OFFSET) for n in STORE))

    def test_manual_pair_rejects_cash_deduction_formula_earning_and_tax_components(self):
        s=self.noncash_settings();pair=STORE[s.component_mapping[0].noncash_offset_component]
        for field,value in [('do_not_include_in_total',0),('do_not_include_in_accounts',1),('type','Earning'),
                            ('depends_on_payment_days',1),('formula','base * 0.01'),('condition','1'),('amount',10),
                            ('disabled',1),('statistical_component',1),('is_tax_applicable',1)]:
            original=pair.get(field);pair[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError): s.validate()
            pair[field]=original
        s.component_mapping[0].noncash_offset_component=s.withholding_component
        with self.assertRaisesRegex(ValueError,'Komponen pajak'): s.validate()

    def test_selected_pair_cannot_also_be_tax_mapping_source(self):
        s=self.noncash_settings();pair=s.component_mapping[0].noncash_offset_component
        s.component_mapping.append(Box(salary_component=pair,treatment='Ignore'))
        with self.assertRaisesRegex(ValueError,'sekaligus'): s.validate()

    def test_selected_pair_link_and_master_are_locked_after_submitted(self):
        s=self.noncash_settings();s._old=Doc(copy.deepcopy(s));self.posted.add(s.name)
        s.component_mapping[0].noncash_offset_component='Different Pair'
        with self.assertRaisesRegex(ValueError,'submitted'): s.validate()
        pair=STORE[s._old.component_mapping[0].noncash_offset_component]
        s.component_mapping[0].noncash_offset_component=pair.name
        pair._old=Doc(copy.deepcopy(pair));self.posted.add(pair.name)
        pair.accounts[0].account='Liability New'
        with self.assertRaisesRegex(ValueError,'dikunci'): self.validation.validate_generated_component(pair)

    def test_legacy_pair_remains_usable_without_creation_or_renaming(self):
        s=self.noncash_settings();row=s.component_mapping[0]
        pair=STORE[row.noncash_offset_component]
        name=self.setup.noncash_component_name(s.name,row.salary_component)
        legacy=Component(copy.deepcopy(pair));legacy.name=name;STORE[name]=legacy
        row.noncash_offset_component=name;before=set(STORE)
        s.validate();s.validate()
        self.assertEqual(row.noncash_offset_component,name)
        self.assertEqual(set(STORE),before)
        self.assertEqual(legacy.accounts[0].account,'Liability BPJS')

    def test_after_migrate_never_creates_or_backfills_noncash_pairs(self):
        calls=[]
        fiscal=types.ModuleType('frappe_hr_pph21.fiscal_year')
        fiscal.backfill_fiscal_year_links=lambda: calls.append('fiscal')
        settings=types.ModuleType('frappe_hr_pph21.settings')
        settings.migrate_settings_links=lambda: calls.append('settings')
        workspace=types.ModuleType('frappe_hr_pph21.workspace')
        workspace.sync_navigation=lambda: calls.append('workspace')
        names=('check_versions','sync_custom_fields','sync_mapping_codes')
        with patch.dict(sys.modules, {'frappe_hr_pph21.fiscal_year':fiscal,
                'frappe_hr_pph21.settings':settings,'frappe_hr_pph21.workspace':workspace}):
            with patch.multiple(self.setup, **{n:(lambda name=n: calls.append(name)) for n in names}):
                self.setup.after_migrate()
        self.assertEqual(calls,['check_versions','sync_custom_fields','sync_mapping_codes',
                               'fiscal','settings','workspace'])

if __name__ == '__main__': unittest.main()
