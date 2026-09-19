import json
from pathlib import Path
import tempfile
import unittest
import urllib.request
import urllib.error
from qgis.core import QgsApplication, QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry
from qgis.PyQt.QtCore import QCoreApplication
from portolan_catalog_builder.i18n import install, tr, language
from portolan_catalog_builder.preview import PreviewServer
from portolan_catalog_builder.domain import CatalogPlan, LayerPlan, FieldPlan, validate_plan
from portolan_catalog_builder.snapshot import snapshot_steps
from portolan_catalog_builder.engine import BuildTask, start_workspace
import test_build

class InvariantTests(unittest.TestCase):
    def test_translation_and_fallback(self):
        for code, expected in [('ja_JP', 'カタログを作成'), ('ja-JP', 'カタログを作成'), ('en_US', 'Build catalog'), ('fr_FR', 'Build catalog')]:
            QgsApplication.setTranslation(code)
            translator = install()
            self.assertEqual(tr('Build catalog'), expected)
            self.assertEqual(tr('An untranslated sentence'), 'An untranslated sentence')
            QCoreApplication.removeTranslator(translator)
        QgsApplication.setTranslation('en')

    def test_range_server_and_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'tile.pmtiles').write_bytes(b'0123456789')
            server = PreviewServer(root)
            try:
                base = server.url('west').split('/_app/')[0]
                request = urllib.request.Request(base + '/tile.pmtiles', headers={'Range': 'bytes=2-5'})
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(response.status, 206)
                    self.assertEqual(response.read(), b'2345')
                    self.assertEqual(response.headers['Content-Range'], 'bytes 2-5/10')
                with urllib.request.urlopen(urllib.request.Request(base + '/tile.pmtiles', method='HEAD')) as response:
                    self.assertEqual(response.headers['Content-Length'], '10')
                with self.assertRaises(urllib.error.HTTPError):
                    urllib.request.urlopen(base + '/%2e%2e/secret')
            finally:
                server.close()

    def test_clip_and_cancel(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            layer = test_build.BuildTests().make_layer()
            plan = LayerPlan(layer.id(), 'parks', 'Parks', pmtiles=False, scope='clip',
                extent=[139.736, 35.666, 139.738, 35.668], extent_crs='EPSG:4326', fields=[FieldPlan('trees', 'trees')])
            result = list(snapshot_steps(layer, plan, Path(tmp) / 'clip.gpkg'))[-1]
            self.assertEqual(result['count'], 1)
            for actual, expected in zip(result['bbox'], plan.extent):
                self.assertAlmostEqual(actual, expected)
            with self.assertRaises(InterruptedError):
                list(snapshot_steps(layer, plan, Path(tmp) / 'cancel.gpkg', lambda: True))

    def test_change_during_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            layer = test_build.BuildTests().make_layer(count=301)
            plan = LayerPlan(layer.id(), 'parks', 'Parks', pmtiles=False, fields=[FieldPlan('trees', 'trees')])
            generator = snapshot_steps(layer, plan, Path(tmp) / 'data.gpkg')
            next(generator)
            layer.startEditing()
            fid = next(layer.getFeatures()).id()
            layer.changeAttributeValue(fid, 1, 99)
            with self.assertRaises(ValueError):
                list(generator)
            layer.rollBack()

    def test_off_only_and_scalar_types(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            layer = QgsVectorLayer('Point?crs=EPSG:4326&field=code:string&field=large:long&field=flag:bool&field=note:string', 'Types', 'memory')
            f = QgsFeature(layer.fields())
            f.setGeometry(QgsGeometry.fromWkt('POINT(139 35)'))
            f.setAttributes(['00123', 9007199254740993, True, None])
            layer.dataProvider().addFeatures([f])
            layer.updateExtents()
            spec = LayerPlan(layer.id(), 'types', 'Scalar types', 'Synthetic scalar types.', pmtiles=False, thumbnail=False,
                fields=[FieldPlan(f.name(), f.name()) for f in layer.fields()])
            plan = CatalogPlan(title='Scalar Types', description='Synthetic test data.', producer='Demo', host='Demo',
                contact='demo@example.org', license='CC0-1.0', output=str(Path(tmp) / 'catalog'), layers=[spec])
            workspace = start_workspace(plan.output)
            result = list(snapshot_steps(layer, spec, workspace / 'snapshots/types.gpkg'))[-1]
            task = BuildTask(plan, workspace, {layer.id(): result}, {}, lambda *args: None)
            self.assertTrue(task.run(), task.error)
            import pyarrow.parquet as pq
            table = pq.read_table(Path(plan.output) / 'types/types.parquet')
            self.assertEqual(table['code'].to_pylist(), ['00123'])
            self.assertEqual(table['large'].to_pylist(), [9007199254740993])
            self.assertEqual(table['flag'].to_pylist(), [True])
            self.assertEqual(table['note'].to_pylist(), [None])
            geo = json.loads(table.schema.metadata[b'geo'])
            self.assertEqual(geo['version'], '1.1.0')
            self.assertIn('covering', geo['columns']['geometry'])
            self.assertFalse(list(Path(plan.output).rglob('*.pmtiles')))
            self.assertTrue(any('already exists' in x for x in validate_plan(plan)))

