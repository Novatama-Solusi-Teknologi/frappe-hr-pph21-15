"""Cleansing boundaries and rollback tests; DB/delete/File services are test doubles."""
import ast
import copy
from hashlib import sha256
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from test_bulk_profiles import Box, load

ROOT = Path(__file__).resolve().parents[1]


class CleanupTest(unittest.TestCase):
    def setUp(self):
        self.docs, self.rows, self.used, self.formulas, self.posted = {}, {}, set(), set(), set()
        self.blocked, self.deleted, self.archived, self.files = set(), [], [], []
        self.snapshots, self.writes = {}, []
        self.frappe = types.ModuleType('frappe')
        self.frappe.LinkExistsError = type('LinkExistsError', (Exception,), {})
        self.frappe.get_doc = self.get_doc
        self.frappe.get_all = self.get_all
        self.frappe.delete_doc = self.delete_doc
        self.frappe.clear_document_cache = lambda *args: None
        self.frappe.db = Box(exists=self.exists, set_value=self.set_value,
                             savepoint=self.savepoint, rollback=self.rollback)
        self.setup = types.ModuleType('frappe_hr_pph21.setup')
        self.setup.NONCASH_OFFSET = 'PPh21 Utang Noncash'
        self.setup.component_abbreviation = lambda n: 'PPH21_NC_' + sha256(n.encode()).hexdigest()[:12]
        self.setup.settings_has_submitted_slips = lambda n: n in self.posted
        self.patch = patch.dict(sys.modules, {'frappe':self.frappe, 'frappe_hr_pph21.setup':self.setup})
        self.patch.start(); self.addCleanup(self.patch.stop)
        self.mod = load('cleanup_test_module', 'frappe_hr_pph21/cleanup.py')

    def legacy(self, token='a', linked=True):
        name = f'PPh21 Utang Noncash [{token * 20}]'
        self.docs[name] = Box(name=name, salary_component_abbr=self.setup.component_abbreviation(name),
            type='Deduction', description='Pasangan jurnal otomatis BPJS; Settings S. Bukan potongan THP/pengurang pajak.',
            accounts=[Box(company='PUP',account='Utang BPJS')])
        if linked:
            self.rows[token] = Box(name=token, parent='S', parenttype='PPh21 Settings',
                parentfield='component_mapping', salary_component='BPJS', noncash_offset_component=name)
        return name

    def get_doc(self, dt, name=None, **kw):
        if isinstance(dt, dict):
            self.assertEqual(dt['doctype'],'File')
            def insert(**kwargs):
                self.assertTrue(kwargs['ignore_permissions']); self.files.append(copy.deepcopy(dt))
            return Box(insert=insert)
        if dt=='Salary Component': return copy.deepcopy(self.docs[name])
        if dt=='PPh21 Settings': return Box(name=name)
        raise AssertionError(dt)

    def get_all(self, dt, **kw):
        if 'or_filters' in kw:
            pattern=kw['or_filters']['formula'][1]
            return [Box(name='FORMULA')] if (dt, pattern) in self.formulas else []
        if dt=='Salary Component':
            return [Box(name=n) for n in sorted(self.docs) if n.startswith(self.setup.NONCASH_OFFSET+' [')]
        if dt=='PPh21 Component Tax Mapping':
            name=kw['filters']['noncash_offset_component']
            return [copy.deepcopy(r) for r in self.rows.values() if r.noncash_offset_component==name]
        raise AssertionError(dt)

    def exists(self, dt, filters): return (dt,filters['salary_component']) in self.used
    def set_value(self, dt, name, field, value, **kw):
        self.assertEqual(dt,'PPh21 Component Tax Mapping');self.assertFalse(kw['update_modified'])
        self.rows[name][field]=value;self.writes.append(name)
    def savepoint(self, name):
        self.snapshots[name]=copy.deepcopy((self.docs,self.rows,self.deleted,self.archived,self.writes))
    def rollback(self, save_point):
        self.docs,self.rows,self.deleted,self.archived,self.writes=copy.deepcopy(self.snapshots[save_point])
    def delete_doc(self, dt, name, **kw):
        self.assertEqual(dt,'Salary Component')
        self.assertEqual(kw,dict(ignore_permissions=True,force=False,delete_permanently=False))
        self.assertFalse(any(r.noncash_offset_component==name for r in self.rows.values()))
        if name in self.blocked: raise self.frappe.LinkExistsError('Other linked record')
        self.deleted.append(name);self.archived.append(self.docs.pop(name))

    def test_dry_run_does_not_modify_master_mapping_or_files(self):
        name=self.legacy();before=copy.deepcopy((self.docs,self.rows))
        result=self.mod.cleanup_unused_noncash()
        self.assertEqual(result['eligible'],[name]);self.assertEqual(result['deleted'],[])
        self.assertEqual((self.docs,self.rows),before)
        self.assertFalse(self.writes or self.snapshots or self.files)

    def test_delete_unused_pairs_detaches_all_settings_and_preserves_other_masters(self):
        name=self.legacy();orphan=self.legacy('b',linked=False)
        self.rows['other']=Box(self.rows['a'],name='other',parent='S2')
        for other in ['Utang BPJS Perusahaan','PPh21 Potongan Pajak','PPh21 Tunjangan Pajak','PPh21 Pengembalian Pajak']:
            self.docs[other]=Box(name=other)
        result=self.mod.run_cleanup_patch()
        self.assertEqual(set(result['deleted']),{name,orphan})
        self.assertEqual(len(result['cleared_mappings']),2)
        self.assertTrue(all(r.noncash_offset_component is None for r in self.rows.values()))
        self.assertEqual(len(self.docs),4);self.assertEqual(len(self.archived),2)
        self.assertEqual(len(self.files),1);self.assertEqual(self.files[0]['is_private'],1)
        self.assertEqual(json.loads(self.files[0]['content'])['deleted'],result['deleted'])
        second=self.mod.run_cleanup_patch()
        self.assertFalse(second['deleted']);self.assertEqual(len(self.files),1)

    def test_salary_details_additional_salary_and_source_mappings_are_preserved(self):
        for i,doctype in enumerate(['Salary Detail','Additional Salary','PPh21 Component Tax Mapping']):
            name=self.legacy('abc'[i]);self.used.add((doctype,name))
        before=copy.deepcopy((self.docs,self.rows))
        result=self.mod.cleanup_unused_noncash(dry_run=False)
        self.assertEqual(len(result['skipped']),3);self.assertFalse(result['deleted'])
        self.assertEqual((self.docs,self.rows),before)

    def test_settings_used_by_submitted_slip_prevents_detaching_pair(self):
        name=self.legacy();self.posted.add('S')
        result=self.mod.cleanup_unused_noncash(dry_run=False)
        self.assertIn(name,self.docs);self.assertEqual(self.rows['a'].noncash_offset_component,name)
        self.assertIn('submitted',result['skipped'][0]['reason'])

    def test_formula_references_are_preserved(self):
        name=self.legacy();abbr=self.docs[name].salary_component_abbr
        self.formulas.add(('Salary Detail',f'%{abbr}%'))
        result=self.mod.cleanup_unused_noncash(dry_run=False)
        self.assertIn(name,self.docs);self.assertIn('formula',result['skipped'][0]['reason'])

    def test_unknown_native_link_restores_mapping_and_continues_other_candidates(self):
        first=self.legacy();second=self.legacy('b');self.blocked.add(first)
        result=self.mod.cleanup_unused_noncash(dry_run=False)
        self.assertEqual(result['deleted'],[second]);self.assertIn(first,self.docs)
        self.assertEqual(self.rows['a'].noncash_offset_component,first)
        self.assertIsNone(self.rows['b'].noncash_offset_component)
        self.assertEqual(result['eligible'],[second]);self.assertEqual(len(self.archived),1)
        self.assertEqual([r['mapping'] for r in result['cleared_mappings']],['b'])

    def test_similar_names_modified_identity_and_unknown_parent_are_not_deleted(self):
        a=self.legacy();self.docs[a].salary_component_abbr='MANUAL'
        b=self.legacy('b');self.docs[b].description='User component'
        self.legacy('c');self.rows['c'].parenttype='Other'
        self.docs['PPh21 Utang Noncash [manual]']=Box(name='PPh21 Utang Noncash [manual]')
        result=self.mod.cleanup_unused_noncash(dry_run=False)
        self.assertEqual(len(result['skipped']),4);self.assertEqual(len(self.docs),4)
        self.assertFalse(self.writes)

    def test_cleanup_patch_is_registered_after_schema_and_delegates_to_reported_cleanup(self):
        lines=(ROOT/'frappe_hr_pph21/patches.txt').read_text().splitlines()
        patch_name='frappe_hr_pph21.patches.v0_8_1_cleanup_noncash'
        self.assertEqual(lines.count(patch_name),1)
        self.assertGreater(lines.index(patch_name),lines.index('[post_model_sync]'))
        tree=ast.parse((ROOT/'frappe_hr_pph21/patches/v0_8_1_cleanup_noncash.py').read_text())
        self.assertTrue(any(isinstance(n,ast.FunctionDef) and n.name=='execute' for n in tree.body))
        called=[]
        module=types.ModuleType('frappe_hr_pph21.cleanup');module.run_cleanup_patch=lambda: called.append(True)
        with patch.dict(sys.modules, {'frappe_hr_pph21.cleanup':module}):
            load('cleanup_patch_test','frappe_hr_pph21/patches/v0_8_1_cleanup_noncash.py').execute()
        self.assertEqual(called,[True])


if __name__=='__main__': unittest.main()
