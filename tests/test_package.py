import ast
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "frappe_hr_pph21"


class PackageTest(unittest.TestCase):
    def test_doctype_schemas_and_controllers(self):
        paths = list((PACKAGE / "frappe_hr_pph21/doctype").glob("*/*.json"))
        self.assertEqual(len(paths), 5)
        for path in paths:
            schema = json.loads(path.read_text())
            names = [row['fieldname'] for row in schema['fields']]
            self.assertEqual(len(names), len(set(names)))
            self.assertEqual(set(names), set(schema['field_order']))
            controller = ast.parse(path.with_suffix('.py').read_text())
            classes = {node.name for node in controller.body if isinstance(node, ast.ClassDef)}
            self.assertIn(schema['name'].replace(' ', '').replace('-', ''), classes)
            if not schema.get('istable'):
                self.assertNotIn('Employee', {r['role'] for r in schema['permissions']})

    def test_hook_paths_exist(self):
        spec = importlib.util.spec_from_file_location('pph21_hooks_check', PACKAGE / 'hooks.py')
        hooks = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hooks)
        self.assertEqual(hooks.required_apps, ['erpnext', 'hrms'])
        paths = [hooks.before_install, hooks.after_install, hooks.after_migrate]
        paths += list(hooks.override_doctype_class.values())
        paths += [p for events in hooks.doc_events.values() for p in events.values()]
        paths += list(hooks.has_permission.values())
        for dotted in paths:
            module, symbol = dotted.rsplit('.', 1)
            path = ROOT / (module.replace('.', '/') + '.py')
            tree = ast.parse(path.read_text())
            self.assertIn(symbol, {node.name for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))})

    def test_workspace_links_and_reports(self):
        workspace = json.loads((PACKAGE / 'frappe_hr_pph21/workspace/frappe_hr_pph21/frappe_hr_pph21.json').read_text())
        blocks = json.loads(workspace['content'])
        self.assertEqual(len(blocks), 7)
        for path in (PACKAGE / 'frappe_hr_pph21/report').glob('*/*.json'):
            report = json.loads(path.read_text())
            self.assertEqual(report['report_type'], 'Script Report')
            self.assertTrue(path.with_suffix('.py').is_file())

    def test_unactivated_defaults(self):
        path = PACKAGE / 'frappe_hr_pph21/doctype/pph21_settings/pph21_settings.json'
        settings = json.loads(path.read_text())
        enabled = next(row for row in settings['fields'] if row['fieldname'] == 'enabled')
        self.assertEqual(enabled['default'], '0')


if __name__ == '__main__':
    unittest.main()
