import json
from pathlib import Path
import tempfile
import unittest
from portolan_catalog_builder.basic_checks import check_catalog


class BasicChecksTests(unittest.TestCase):
    def test_missing_invalid_and_escaping_references(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('README.md', 'AGENTS.md', 'VALIDATION.md'):
                (root / name).write_text('Documentation')
            document = {'type': 'Catalog', 'id': 'demo', 'description': 'Demo',
                        'stac_version': '1.1.0', 'links': [{'href': './README.md'}]}
            path = root / 'catalog.json'
            path.write_text(json.dumps(document))
            self.assertEqual(check_catalog(root), [])
            for href in ('./missing.parquet', '../outside.json', '%2e%2e/outside.json'):
                document['links'] = [{'href': href}]
                path.write_text(json.dumps(document))
                self.assertTrue(check_catalog(root), href)
            path.write_text('{broken')
            self.assertTrue(check_catalog(root))
