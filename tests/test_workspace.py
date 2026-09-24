"""Upgrade navigation without duplicate menus or overwriting unrelated workspaces."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from test_bulk_profiles import Box


class WorkspaceMigrationTest(unittest.TestCase):
    def setUp(self):
        self.records = {'Frappe HR PPh21': Box(module='Frappe HR PPh21', public=1, content='custom'),
                        'Child': Box(module='Other', public=1, parent_page='Frappe HR PPh21')}
        self.renames=[]
        frappe=types.ModuleType('frappe')
        def set_value(dt,name,field,value=None):
            self.records[name].update(field if isinstance(field,dict) else {field:value})
        def rename(dt,old,new,**kwargs):
            self.records[new]=self.records.pop(old);self.renames.append((old,new))
        frappe.db=Box(get_value=lambda dt,name,*a,**kw:self.records.get(name),
                      set_value=set_value,exists=lambda dt,name:name in self.records)
        frappe.rename_doc=rename
        frappe.get_all=lambda dt,filters,**kw:[name for name,row in self.records.items() if all(row.get(k)==v for k,v in filters.items())]
        frappe.clear_cache=lambda **kw:None
        frappe.throw=lambda msg:(_ for _ in ()).throw(ValueError(msg))
        spec=importlib.util.spec_from_file_location('workspace_test_module',Path(__file__).resolve().parents[1]/'frappe_hr_pph21/workspace.py')
        with patch.dict(sys.modules,{'frappe':frappe}):
            self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
    def test_existing_menu_is_renamed_once_preserving_content_and_children(self):
        for _ in range(2):
            self.module.before_migrate();self.module.sync_navigation()
        self.assertEqual(self.renames,[('Frappe HR PPh21','PPh 21')])
        self.assertNotIn('Frappe HR PPh21',self.records)
        self.assertEqual(self.records['PPh 21'].content,'custom')
        self.assertEqual(self.records['PPh 21'].parent_page,'HR')
        self.assertEqual(self.records['Child'].parent_page,'PPh 21')
    def test_unrelated_existing_workspace_is_not_overwritten(self):
        self.records['PPh 21']=Box(module='Other',public=1)
        with self.assertRaisesRegex(ValueError,'workspace lain'):self.module.before_migrate()
        self.assertEqual(self.records['PPh 21'].module,'Other')
        self.assertEqual(self.renames,[])
    def test_existing_duplicate_is_hidden_without_deleting_its_content(self):
        self.records['PPh 21']=Box(module='Frappe HR PPh21',public=1)
        self.module.before_migrate();self.module.sync_navigation()
        self.assertEqual(self.records['Frappe HR PPh21'].is_hidden,1)
        self.assertEqual(self.records['Frappe HR PPh21'].content,'custom')
        self.assertEqual(self.records['PPh 21'].parent_page,'HR')

if __name__ == '__main__': unittest.main()
