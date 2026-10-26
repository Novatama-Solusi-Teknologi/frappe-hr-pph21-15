"""Upgrade routing and preservation with in-memory Frappe services."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from test_bulk_profiles import Box, load
import test_settings as fixtures


class NoncashMigrationTest(unittest.TestCase):
    def setUp(self):
        self.case=fixtures.SettingsTest();self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.settings=self.case.noncash_settings()
        self.source=fixtures.STORE['BPJS']
        self.source.accounts[0].name='ACC-1'
        self.source.accounts[0].pph21_noncash_payable_account=None
        self.files=[];self.writes=[]
        f=self.case.frappe
        f.ValidationError=ValueError;f.DoesNotExistError=KeyError
        f.get_all=lambda dt,**kw: [Box(name=s.name,company=s.company) for s in self.case.saved_settings]
        original=f.get_doc
        def get_doc(dt,name=None,**kw):
            if isinstance(dt,dict):
                def insert(**kw): self.files.append(dt)
                return Box(insert=insert)
            if dt=='PPh21 Settings': return next(s for s in self.case.saved_settings if s.name==name)
            return original(dt,name,**kw)
        f.get_doc=get_doc
        f.clear_document_cache=lambda *a: None
        def set_value(dt,name,field,value,**kw):
            self.assertEqual(dt,'Salary Component Account');self.assertFalse(kw['update_modified'])
            self.source.accounts[0][field]=value;self.writes.append((name,value))
        f.db.set_value=set_value
        with patch.dict(sys.modules,{'frappe_hr_pph21.setup':self.case.setup}):
            self.module=load('noncash_migration_test','frappe_hr_pph21/noncash_migration.py')

    def test_unique_account_backfills_without_modifying_pair_or_mapping_and_rerun_is_noop(self):
        pair=fixtures.STORE[self.settings.component_mapping[0].noncash_offset_component]
        before=copy.deepcopy((pair,self.settings))
        report=self.module.execute()
        self.assertEqual(report['copied'][0]['payable_account'],'Liability BPJS')
        self.assertEqual(self.source.accounts[0].account,'Expense BPJS')
        self.assertEqual((pair,self.settings),before)
        self.assertEqual(len(self.writes),1);self.assertEqual(self.files[0]['is_private'],1)
        self.assertEqual(json.loads(self.files[0]['content']),report)
        self.assertEqual(self.module.execute(),{'copied':[],'skipped':[]})
        self.assertEqual(len(self.files),1)

    def test_conflicting_accounts_across_settings_are_not_guessed(self):
        other=copy.deepcopy(self.settings);other.name='OTHER'
        self.case.saved_settings.append(other)
        pair=copy.deepcopy(fixtures.STORE['Utang BPJS Perusahaan']);pair.name='Other Pair'
        pair.accounts[0].account='Liability Other';fixtures.STORE[pair.name]=pair
        other.component_mapping[0].noncash_offset_component=pair.name
        result=self.module.execute()
        self.assertFalse(self.writes);self.assertIn('berbeda',result['skipped'][0]['reason'])

    def test_existing_different_account_and_duplicate_company_rows_are_preserved(self):
        self.source.accounts[0].pph21_noncash_payable_account='Liability Manual'
        result=self.module.execute();self.assertFalse(self.writes)
        self.assertIn('tidak ditimpa',result['skipped'][0]['reason'])
        self.source.accounts.append(Box(company='PUP',account='Liability BPJS'))
        result=self.module.execute();self.assertFalse(self.writes)
        self.assertIn('tepat satu akun',result['skipped'][0]['reason'])
        self.assertEqual(len(self.source.accounts),2)

    def test_fresh_site_without_legacy_mappings_has_no_data_changes(self):
        self.case.saved_settings=[]
        self.assertEqual(self.module.execute(),{'copied':[],'skipped':[]})
        self.assertFalse(self.writes or self.files)

    def test_backfill_registered_before_old_cleanup_so_skipped_versions_keep_accounts(self):
        root=Path(__file__).resolve().parents[1]
        text=(root/'frappe_hr_pph21/patches.txt').read_text()
        self.assertLess(text.index('v0_10_0_noncash_accounts'),text.index('v0_8_1_cleanup_noncash'))
        self.assertLess(text.index('[post_model_sync]'),text.index('v0_10_0_noncash_accounts'))


if __name__=='__main__': unittest.main()
