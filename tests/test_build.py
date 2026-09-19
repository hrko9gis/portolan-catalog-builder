import json
from pathlib import Path
import tempfile
import unittest
from qgis.core import QgsVectorLayer, QgsFeature, QgsGeometry, QgsProject
from portolan_catalog_builder.domain import CatalogPlan, LayerPlan, FieldPlan, validate_plan
from portolan_catalog_builder.snapshot import snapshot_steps
from portolan_catalog_builder.styles import extract_style
from portolan_catalog_builder.engine import BuildTask, start_workspace

class BuildTests(unittest.TestCase):
    def make_layer(self, name='Parks', count=2):
        layer = QgsVectorLayer('Polygon?crs=EPSG:4326&field=name:string&field=trees:integer&field=secret:string', name, 'memory')
        for i in range(count):
            f = QgsFeature(layer.fields())
            x = 139.735 + 0.008 * i
            f.setGeometry(QgsGeometry.fromWkt(f'POLYGON(({x} 35.665,{x+.004} 35.665,{x+.004} 35.669,{x} 35.669,{x} 35.665))'))
            f.setAttributes([f'Park {i}', 10 * (i+1), 'DO_NOT_EXPORT'])
            layer.dataProvider().addFeatures([f])
        layer.updateExtents()
        return layer

    def test_build_mixed(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            west, east = self.make_layer(), self.make_layer('East', 1)
            plans = [LayerPlan(l.id(), ident, l.name(), 'Fictional parks for export testing.', pmtiles=tiles, thumbnail=False,
                fields=[FieldPlan('name', 'name'), FieldPlan('trees', 'trees'), FieldPlan('secret', 'secret', include=False)])
                for l, ident, tiles in [(west, 'west', True), (east, 'east', False)]]
            plan = CatalogPlan(title='Parks Demo', description='Fictional parks used for testing.', producer='Demo', host='Demo',
                contact='demo@example.org', license='CC0-1.0', output=str(Path(tmp) / 'catalog'), layers=plans)
            self.assertEqual(validate_plan(plan), [])
            workspace = start_workspace(plan.output)
            snapshots, styles = {}, {}
            for layer, item in zip((west, east), plans):
                for result in snapshot_steps(layer, item, workspace / 'snapshots' / (item.id + '.gpkg')):
                    if result.get('complete'):
                        snapshots[item.layer_id] = result
                if item.pmtiles:
                    styles[item.layer_id] = extract_style(layer, item)
            task = BuildTask(plan, workspace, snapshots, styles, lambda *args: None)
            success = task.run()
            if not success:
                print('BUILD ERROR', task.error)
                for file in ('validation.json', 'validator.log'):
                    path = workspace / file
                    if path.exists():
                        print(path.read_text(encoding='utf-8')[:14000])
            self.assertTrue(success, task.error)
            root = Path(plan.output)
            self.assertTrue((root / 'west/west.pmtiles').is_file())
            self.assertFalse((root / 'east/east.pmtiles').exists())
            self.assertFalse((root / 'east/styles').exists())
            import pyarrow.parquet as pq
            data = pq.read_table(root / 'west/west.parquet')
            self.assertEqual(data.num_rows, 2)
            self.assertNotIn('secret', data.column_names)
            self.assertEqual(sum(data['trees'].to_pylist()), 30)
            east_json = json.loads((root / 'east/collection.json').read_text())
            self.assertFalse(any(l['rel'] == 'pmtiles' for l in east_json['links']))
            self.assertTrue(task.report['basic_checks']['status'] == 'passed')
            self.assertTrue(task.report['detailed_validation']['status'] == 'not_run')
            self.assertNotIn('passed', task.report)
            self.assertEqual(task.report['build_status'], 'completed')
            self.assertIn('Detailed validation', (root / 'VALIDATION.md').read_text(encoding='utf-8'))
            self.assertIn('validation-guide', east_json['assets'])
            from unittest.mock import patch
            plan.output = str(Path(tmp) / 'rejected')
            rejected_workspace = start_workspace(plan.output)
            rejected = BuildTask(plan, rejected_workspace, snapshots, styles, lambda *args: None)
            with patch('portolan_catalog_builder.engine.check_catalog', return_value=[
                    {'severity': 'error', 'rule_id': 'EXPORT-FILES', 'path': 'missing', 'message': 'Missing asset'}]):
                self.assertFalse(rejected.run())
            self.assertFalse(Path(plan.output).exists())
            self.assertEqual(rejected.report['basic_checks']['status'], 'failed')
            self.assertEqual(rejected.report['detailed_validation']['status'], 'not_run')

    def test_selected_and_edited(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            layer = self.make_layer()
            layer.startEditing()
            fid = next(layer.getFeatures()).id()
            layer.changeAttributeValue(fid, 1, 55)
            layer.selectByIds([fid])
            plan = LayerPlan(layer.id(), 'parks', 'Parks', scope='selected', pmtiles=False,
                             fields=[FieldPlan('trees', 'tree_count')])
            result = list(snapshot_steps(layer, plan, Path(tmp) / 'snapshot.gpkg'))[-1]
            self.assertEqual(result['count'], 1)
            copy = QgsVectorLayer(result['path'] + '|layername=parks', 'copy', 'ogr')
            self.assertEqual(next(copy.getFeatures())['tree_count'], 55)
            copy = None
            self.assertTrue(layer.isEditable())
            layer.rollBack()

    def test_invalid_settings(self):
        plan = CatalogPlan(layers=[LayerPlan('x', '../unsafe', 'Bad', fields=[])])
        self.assertTrue(validate_plan(plan))
        with self.assertRaises(ValueError):
            CatalogPlan.from_dict({'settings_schema_version': 500})
