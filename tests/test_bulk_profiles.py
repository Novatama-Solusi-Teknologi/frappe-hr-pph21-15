"""Bulk/controller behavior with a transactional in-memory Frappe double.
Real database, Desk, and Company User Permissions still require staging UAT.
"""
import copy
from datetime import date
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PROFILE = 'PPh21 Employee Tax Profile'


class Box(dict):
    def __getattr__(self, key): return self.get(key)
    def __setattr__(self, key, value): self[key] = value


class Doc(Box):
    def check_permission(self, kind):
        if self.get('denied'):
            raise PermissionError('Employee/profile permission denied')
    def get_doc_before_save(self): return self.get('_old')
    def insert(self):
        self.before_validate()
        self.autoname()
        self.validate()
        ENV.profiles[self.name] = copy.deepcopy(dict(self))
        return self
    def save(self):
        self.check_permission('write')
        self._old = Box(copy.deepcopy(ENV.profiles[self.name]))
        self.before_validate()
        self.validate()
        ENV.profiles[self.name] = copy.deepcopy({k: v for k, v in self.items() if k != '_old'})
        return self


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Environment:
    def __init__(self):
        self.profiles, self.locked, self.read_locks, self.rollbacks = {}, set(), [], 0
        self.employees = {
            'EMP-A': Doc(company='Company A', employee_name='Alice', custom_ptkp='TK/0', date_of_joining='2026-01-01'),
            'EMP-B': Doc(company='Company B', employee_name='Bob', custom_ptkp='K/1', date_of_joining='2026-01-01'),
        }
        self.settings = {'Settings A': Doc(name='Settings A',company='Company A',enabled=1),
                         'Settings B': Doc(name='Settings B',company='Company B',enabled=1)}
        self.fiscal_years = {f'FY-{year}': Doc(name=f'FY-{year}', year_start_date=f'{year}-01-01', year_end_date=f'{year}-12-31', disabled=0, companies=[]) for year in (2024,2025,2026,2027)}
        self.frappe = types.ModuleType('frappe')
        self.frappe.whitelist = lambda: lambda fn: fn
        self.frappe.validate_and_sanitize_search_inputs = lambda fn: fn
        self.frappe.only_for = lambda roles: None
        self.frappe.throw = lambda msg: self.fail(msg)
        self.frappe.get_doc = self.get_doc
        self.frappe.new_doc = lambda dt: self.profile_cls(doctype=dt, opening_reference='')
        self.frappe.get_list = self.get_list
        self.frappe.db = Box(exists=self.exists, savepoint=self.savepoint, rollback=self.rollback, sql=self.profile_sql)
        utils = types.ModuleType('frappe.utils')
        utils.cint = lambda v: int(v or 0)
        utils.getdate = lambda v=None: date.fromisoformat(str(v)[:10]) if v else date(2026,9,23)
        docmod = types.ModuleType('frappe.model.document'); docmod.Document = Doc
        setup = types.ModuleType('frappe_hr_pph21.setup'); setup.COMPONENTS = {'PPh21 Tunjangan Pajak': None}; setup.NONCASH_OFFSET = 'PPh21 Utang Noncash'
        self.patcher = patch.dict(sys.modules, {'frappe': self.frappe, 'frappe.utils': utils,
            'frappe.model.document': docmod, 'frappe_hr_pph21.setup': setup})
        self.patcher.start()
        self.queries = load('bulk_queries_test', 'frappe_hr_pph21/queries.py')
        self.fiscal = load('fiscal_year_test', 'frappe_hr_pph21/fiscal_year.py')
        self.settings_helper = load('settings_bulk_test', 'frappe_hr_pph21/settings.py')
        self.query_patcher = patch.dict(sys.modules, {'frappe_hr_pph21.settings': self.settings_helper, 'frappe_hr_pph21.queries': self.queries, 'frappe_hr_pph21.fiscal_year': self.fiscal})
        self.query_patcher.start()
        self.profile_cls = load('bulk_profile_test', 'frappe_hr_pph21/frappe_hr_pph21/doctype/pph21_employee_tax_profile/pph21_employee_tax_profile.py').PPh21EmployeeTaxProfile
        self.bulk_cls = load('bulk_controller_test', 'frappe_hr_pph21/frappe_hr_pph21/doctype/bulk_pph21_employee_tax_profile/bulk_pph21_employee_tax_profile.py').BulkPPh21EmployeeTaxProfile
    def close(self): self.query_patcher.stop(); self.patcher.stop()
    def profile_sql(self, query, args):
        if 'tabSalary Slip' in query:
            return [('SLIP',)] if args[0] in self.locked else []
        return []
    @staticmethod
    def fail(msg): raise ValueError(msg)
    def get_doc(self, dt, name, **kw):
        if kw.get('for_update'): self.read_locks.append((dt,name))
        if dt == 'PPh21 Settings': return self.settings[name]
        if dt == 'Employee': return self.employees[name]
        if dt == 'Fiscal Year': return self.fiscal_years[name]
        if dt == PROFILE: return self.profile_cls(copy.deepcopy(self.profiles[name]))
        raise AssertionError(dt)
    def exists(self, dt, filters):
        if dt == 'Salary Slip': return filters['pph21_tax_profile'] in self.locked
        for name, profile in self.profiles.items():
            if profile['employee'] == filters['employee'] and profile['tax_year'] == filters['tax_year']:
                if 'name' not in filters or name != filters['name'][1]: return name
        return None
    def savepoint(self, name): self.snapshot = copy.deepcopy(self.profiles)
    def rollback(self, **kw): self.profiles = self.snapshot; self.rollbacks += 1
    def get_list(self, dt, **kwargs):
        if dt == 'PPh21 Settings':
            return [r.name for r in self.settings.values() if r.company == kwargs['filters']['company'] and r.enabled and not r.denied][:kwargs['page_length']]
        return self.record_query(kwargs)
    def record_query(self, kwargs):
        self.query = kwargs
        return [Box(name='Gaji Pokok',salary_component_abbr='GP',type='Earning')]
    def batch(self, names=('EMP-A','EMP-B')):
        return self.bulk_cls(default_fiscal_year='FY-2026', default_method='Gross Up', docstatus=0,
            confirm_standard_assumptions=1, employees=[Box(idx=i,employee=name,tax_id='1234567890123456') for i,name in enumerate(names,1)])
    def submit(self, doc):
        doc.before_validate(); doc.validate(); doc.docstatus=1; doc.before_submit()


class BulkProfileTest(unittest.TestCase):
    def setUp(self):
        global ENV
        ENV = self.env = Environment()
        self.addCleanup(self.env.close)

    def test_defaults_company_and_ptkp_are_employee_derived(self):
        batch = self.env.batch()
        batch.employees[0].company = 'Spoofed'
        batch.before_validate(); batch.validate()
        self.assertEqual(batch.employees[0].company,'Company A')
        self.assertEqual(batch.employees[1].company,'Company B')
        self.assertEqual(batch.employees[1].ptkp_status,'K/1')
        self.assertEqual(batch.employees[0].method,'Gross Up')
        self.assertEqual(self.env.profiles,{})  # draft cannot create profiles

    def test_missing_custom_ptkp_needs_manual_selection(self):
        del self.env.employees['EMP-A']['custom_ptkp']
        batch = self.env.batch(('EMP-A',)); batch.before_validate()
        with self.assertRaisesRegex(ValueError,'PTKP'): batch.validate()
        batch.employees[0].ptkp_status='TK/2'; batch.validate()

    def test_ptkp_normalization_and_no_guess_for_unknown(self):
        self.env.employees['EMP-A'].custom_ptkp=' k  /  2 '
        self.assertEqual(self.env.queries.employee_values('EMP-A')['ptkp_status'],'K/2')
        self.env.employees['EMP-A'].custom_ptkp='K/I/3'
        self.assertEqual(self.env.queries.employee_values('EMP-A')['ptkp_status'],'')

    def test_duplicate_employee_year_rejected(self):
        batch = self.env.batch(('EMP-A','EMP-A')); batch.before_validate()
        with self.assertRaisesRegex(ValueError,'duplikat'): batch.validate()

    def test_same_employee_different_years_allowed(self):
        batch = self.env.batch(('EMP-A','EMP-A'))
        self.env.employees['EMP-A'].date_of_joining='2025-01-01'
        batch.employees[1].fiscal_year='FY-2025'
        self.env.submit(batch)
        self.assertEqual(len(self.env.profiles),2)

    def test_invalid_year_id_method_and_batch_limit(self):
        for key,value,message in [('tax_year',2027,'tahun pajak'),('tax_id','12','NIK'),('method','Net','Gross')]:
            with self.subTest(key=key):
                batch=self.env.batch(('EMP-A',)); batch.before_validate(); batch.employees[0][key]=value
                with self.assertRaisesRegex(ValueError,message): batch.validate()
        batch=self.env.batch(('EMP-A',)*201)
        with self.assertRaisesRegex(ValueError,'200'): batch.validate()

    def test_confirmation_required_before_submit(self):
        for value in (0, '0', None):
            batch=self.env.batch(); batch.confirm_standard_assumptions=value
            with self.assertRaisesRegex(ValueError,'Konfirmasikan'): self.env.submit(batch)
        self.assertEqual(self.env.profiles,{})

    def test_create_profiles_with_standard_defaults_no_employee_activation(self):
        batch=self.env.batch(); self.env.submit(batch)
        self.assertEqual(len(self.env.profiles),2)
        profile=self.env.profiles['EMP-A-2026']
        for key in ('resident_full_year','permanent_employee'): self.assertEqual(profile[key],1)
        self.assertEqual(profile['tax_identity_validated'],0)
        self.assertEqual(profile['facility'],'Normal')
        self.assertEqual(profile['opening_gross'],0)
        self.assertEqual(profile['ter_category'],'A')
        self.assertIsNone(self.env.employees['EMP-A'].pph21_enabled)
        self.assertEqual(batch.employees[0].result,'Dibuat')

    def test_existing_profile_preserves_opening_balances(self):
        self.env.submit(self.env.batch(('EMP-A',)))
        stored=self.env.profiles['EMP-A-2026']
        stored.update(opening_through_month=8,opening_gross=80_000_000,opening_tax=1_600_000,opening_reference='REKAP-08')
        batch=self.env.batch(('EMP-A',)); batch.employees[0].method='Gross'
        self.env.submit(batch)
        self.assertEqual(self.env.profiles['EMP-A-2026']['opening_gross'],80_000_000)
        self.assertEqual(self.env.profiles['EMP-A-2026']['opening_reference'],'REKAP-08')
        self.assertEqual(batch.employees[0].result,'Diperbarui')

    def test_repeat_batch_unchanged_and_locked_profile_unchanged_allowed(self):
        self.env.submit(self.env.batch(('EMP-A',)))
        self.env.locked.add('EMP-A-2026')
        batch=self.env.batch(('EMP-A',)); self.env.submit(batch)
        self.assertEqual(len(self.env.profiles),1)
        self.assertEqual(batch.employees[0].result,'Tidak berubah')

    def test_locked_profile_change_rolls_back_entire_batch(self):
        self.env.submit(self.env.batch(('EMP-B',)))
        self.env.locked.add('EMP-B-2026')
        batch=self.env.batch(); batch.employees[1].method='Gross'
        with self.assertRaisesRegex(ValueError,'submitted'): self.env.submit(batch)
        self.assertNotIn('EMP-A-2026',self.env.profiles)
        self.assertEqual(self.env.profiles['EMP-B-2026']['method'],'Gross Up')
        self.assertEqual(self.env.rollbacks,1)

    def test_later_invalid_join_date_rolls_back_earlier_insert(self):
        self.env.employees['EMP-B'].date_of_joining='2027-01-01'
        with self.assertRaisesRegex(ValueError,'tanggal mulai'): self.env.submit(self.env.batch())
        self.assertEqual(self.env.profiles,{})

    def test_employee_permission_is_enforced_before_defaults(self):
        self.env.employees['EMP-B'].denied=True
        with self.assertRaises(PermissionError): self.env.batch().before_validate()
        with self.assertRaises(PermissionError): self.env.queries.employee_tax_defaults('EMP-B')

    def test_custom_role_with_employee_read_can_load_defaults(self):
        roles = {'PUP Payroll Operator'}
        def only_for(allowed_roles):
            if not roles.intersection(allowed_roles):
                raise PermissionError('User does not have the hard-coded roles')
        self.env.frappe.only_for = only_for
        self.env.employees['EMP-A'].tax_id = 'private-not-returned'
        self.assertEqual(self.env.queries.employee_tax_defaults('EMP-A'), {
            'company': 'Company A', 'employee_name': 'Alice', 'ptkp_status': 'TK/0',
        })
        # A custom role still cannot read an Employee outside its permitted scope.
        self.env.employees['EMP-B'].denied = True
        with self.assertRaisesRegex(PermissionError, 'Employee/profile permission denied'):
            self.env.queries.employee_tax_defaults('EMP-B')

    def test_existing_profile_permission_enforced(self):
        self.env.submit(self.env.batch(('EMP-B',)))
        self.env.profiles['EMP-B-2026']['denied']=True
        with self.assertRaises(PermissionError): self.env.submit(self.env.batch())
        self.assertNotIn('EMP-A-2026',self.env.profiles)

    def test_component_search_uses_permission_aware_list_and_code(self):
        found=self.env.queries.salary_component_query('Salary Component','GP','name',0,999)
        self.assertEqual(found,[['Gaji Pokok','GP','Earning']])
        self.assertEqual(self.env.query['page_length'],50)
        self.assertIn('salary_component_abbr',self.env.query['or_filters'])
        self.assertTrue(any(f[0]=='name' for f in self.env.query['filters']))

    def test_batch_cannot_be_cancelled_as_if_profiles_were_undone(self):
        with self.assertRaisesRegex(ValueError,'tidak dapat dibatalkan'): self.env.batch().before_cancel()

    def test_batch_read_requires_access_to_every_employee(self):
        self.env.frappe.has_permission = lambda dt, perm, doc, user: doc != 'EMP-B'
        self.assertFalse(self.env.queries.bulk_profile_permission(self.env.batch(), user='limited'))
        self.assertTrue(self.env.queries.bulk_profile_permission(self.env.batch(('EMP-A',)), user='limited'))


    def test_fiscal_year_uses_master_dates_not_record_name_or_client_number(self):
        master = self.env.fiscal_years.pop('FY-2026')
        master.name = 'Periode Payroll PUP'
        self.env.fiscal_years[master.name] = master
        batch = self.env.batch(('EMP-A',))
        batch.default_fiscal_year = master.name
        batch.default_tax_year = 1900
        batch.employees[0].fiscal_year = master.name
        batch.employees[0].tax_year = 1900
        self.env.submit(batch)
        self.assertEqual(batch.default_tax_year, 2026)
        self.assertEqual(batch.employees[0].tax_year, 2026)
        self.assertIn('EMP-A-2026', self.env.profiles)

    def test_individual_autoname_resolves_year_before_normal_validation(self):
        profile = self.env.profile_cls(employee='EMP-A', fiscal_year='FY-2026', ptkp_status='TK/0')
        profile.autoname()
        self.assertEqual(profile.name, 'EMP-A-2026')

    def test_fiscal_year_required_disabled_noncalendar_and_unsupported_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Pilih Fiscal Year'):
            self.env.fiscal.tax_year_from_fiscal_year('')
        self.env.fiscal_years['FY-2026'].disabled = 1
        with self.assertRaisesRegex(ValueError, 'tidak aktif'):
            self.env.fiscal.tax_year_from_fiscal_year('FY-2026')
        self.env.fiscal_years['FY-2026'].disabled = 0
        self.env.fiscal_years['FY-2026'].year_start_date = '2026-04-01'
        with self.assertRaisesRegex(ValueError, '1 Januari'):
            self.env.fiscal.tax_year_from_fiscal_year('FY-2026')
        with self.assertRaisesRegex(ValueError, '2024-2026'):
            self.env.fiscal.tax_year_from_fiscal_year('FY-2027')

    def test_fiscal_year_company_and_read_permissions_enforced(self):
        fy = self.env.fiscal_years['FY-2026']
        fy.companies = [Box(company='Company A')]
        self.assertEqual(self.env.fiscal.tax_year_from_fiscal_year(fy.name, 'Company A'),2026)
        with self.assertRaisesRegex(ValueError, 'Company'):
            self.env.submit(self.env.batch())
        self.assertEqual(self.env.profiles,{})
        fy.denied = True
        with self.assertRaises(PermissionError): self.env.fiscal.tax_year_from_fiscal_year(fy.name)

    def test_empty_identity_is_allowed_and_not_marked_verified(self):
        batch = self.env.batch(('EMP-A',))
        batch.employees[0].tax_id = '   '
        self.env.submit(batch)
        profile = self.env.profiles['EMP-A-2026']
        self.assertEqual(profile['tax_id'],'')
        self.assertEqual(profile['tax_identity_validated'],0)
        individual = self.env.get_doc(PROFILE,'EMP-A-2026')
        individual.tax_identity_validated = 1
        individual.save()
        self.assertEqual(individual.tax_identity_validated,0)

    def test_empty_bulk_identity_preserves_existing_identity(self):
        self.env.submit(self.env.batch(('EMP-A',)))
        batch = self.env.batch(('EMP-A',))
        batch.employees[0].tax_id = ''
        self.env.submit(batch)
        self.assertEqual(self.env.profiles['EMP-A-2026']['tax_id'],'1234567890123456')
        self.assertEqual(batch.employees[0].result,'Tidak berubah')

    def test_changed_identity_is_not_automatically_verified(self):
        self.env.submit(self.env.batch(('EMP-A',)))
        self.env.profiles['EMP-A-2026']['tax_identity_validated'] = 1
        batch = self.env.batch(('EMP-A',))
        batch.employees[0].tax_id = '0123456789012345'
        self.env.submit(batch)
        self.assertEqual(self.env.profiles['EMP-A-2026']['tax_id'],'0123456789012345')
        self.assertEqual(self.env.profiles['EMP-A-2026']['tax_identity_validated'],0)

    def test_legacy_row_different_year_requires_explicit_fiscal_year(self):
        batch = self.env.batch(('EMP-A',))
        batch.employees[0].tax_year = 2025
        with self.assertRaisesRegex(ValueError,'profil lama'): batch.before_validate()

    def test_fiscal_year_backfill_preserves_values_and_skips_ambiguity(self):
        self.env.submit(self.env.batch(('EMP-A',)))
        profile = self.env.profiles['EMP-A-2026']
        del profile['fiscal_year']
        before = copy.deepcopy(profile)
        updates=[]
        def all_records(dt, **kwargs):
            if dt == 'Fiscal Year': return list(self.env.fiscal_years)
            if dt == PROFILE: return [Box(p) for p in self.env.profiles.values() if not p.get('fiscal_year')]
            return []
        def set_value(dt, name, field, value, **kwargs):
            self.assertFalse(kwargs['update_modified'])
            self.env.profiles[name][field] = value
            updates.append((name,field,value))
        self.env.frappe.get_all = all_records
        self.env.frappe.db.set_value = set_value
        self.env.fiscal_years['Other'] = Doc(self.env.fiscal_years['FY-2026'])
        self.env.fiscal_years['Other'].name = 'Other'
        self.env.fiscal.backfill_fiscal_year_links()
        self.assertEqual(updates,[])
        del self.env.fiscal_years['Other']
        self.env.fiscal.backfill_fiscal_year_links()
        self.assertEqual(profile['fiscal_year'],'FY-2026')
        self.assertEqual({k:v for k,v in profile.items() if k!='fiscal_year'},before)
        self.env.fiscal.backfill_fiscal_year_links()
        self.assertEqual(len(updates),1)

    def test_settings_must_be_explicit_when_multiple_choices_exist(self):
        self.env.settings['Settings A2']=Doc(name='Settings A2',company='Company A',enabled=1)
        batch=self.env.batch(('EMP-A',))
        with self.assertRaisesRegex(ValueError,'Pilih PPh21 Settings'): self.env.submit(batch)
        self.assertEqual(self.env.profiles,{})
        batch=self.env.batch(('EMP-A',));batch.employees[0].pph21_settings='Settings A2'
        self.env.submit(batch)
        self.assertEqual(self.env.profiles['EMP-A-2026']['pph21_settings'],'Settings A2')

    def test_settings_wrong_company_disabled_and_denied_rejected(self):
        batch=self.env.batch(('EMP-A',));batch.employees[0].pph21_settings='Settings B'
        with self.assertRaisesRegex(ValueError,'Company'): self.env.submit(batch)
        batch.employees[0].pph21_settings='Settings A';self.env.settings['Settings A'].enabled=0
        with self.assertRaisesRegex(ValueError,'Aktifkan'): self.env.submit(batch)
        self.env.settings['Settings A'].enabled=1;self.env.settings['Settings A'].denied=True
        with self.assertRaises(PermissionError): self.env.submit(batch)
        self.assertEqual(self.env.profiles,{})

    def test_blank_bulk_settings_preserves_selected_profile_settings(self):
        self.env.submit(self.env.batch(('EMP-A',)))
        self.env.settings['Settings A2']=Doc(name='Settings A2',company='Company A',enabled=1)
        batch=self.env.batch(('EMP-A',));self.env.submit(batch)
        self.assertEqual(batch.employees[0].pph21_settings,'Settings A')
        self.assertEqual(batch.employees[0].result,'Tidak berubah')
        self.env.locked.add('EMP-A-2026')
        batch=self.env.batch(('EMP-A',));batch.employees[0].pph21_settings='Settings A2'
        with self.assertRaisesRegex(ValueError,'submitted'): self.env.submit(batch)
        self.assertEqual(self.env.profiles['EMP-A-2026']['pph21_settings'],'Settings A')

    def test_register_filter_resolves_master_year(self):
        self.env.frappe._dict = Box
        report = load('register_fiscal_test','frappe_hr_pph21/frappe_hr_pph21/report/pph21_register/pph21_register.py')
        report.execute({'company':'Company A','fiscal_year':'FY-2026'})
        self.assertEqual(self.env.query['filters']['pph21_tax_year'],2026)


if __name__ == '__main__': unittest.main()
