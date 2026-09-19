from pathlib import Path
import tempfile
import unittest
from qgis.core import QgsField, QgsFeature, QgsGeometry, QgsVectorLayer, QgsVectorLayerJoinInfo, QgsProject
from qgis.PyQt.QtCore import QVariant, QDate, QDateTime, Qt
from portolan_catalog_builder.domain import LayerPlan, FieldPlan
from portolan_catalog_builder.snapshot import snapshot_steps

class SnapshotFieldTests(unittest.TestCase):
    def test_expression_and_dates(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            layer = QgsVectorLayer('Point?crs=EPSG:4326', 'Dates', 'memory')
            layer.dataProvider().addAttributes([QgsField('value', QVariant.Int), QgsField('day', QVariant.Date), QgsField('observed', QVariant.DateTime)])
            layer.updateFields()
            feature = QgsFeature(layer.fields())
            feature.setGeometry(QgsGeometry.fromWkt('POINT(139 35)'))
            feature.setAttributes([4, QDate(2026, 9, 16), QDateTime.fromString('2026-09-16T03:00:00Z', Qt.ISODate)])
            layer.dataProvider().addFeatures([feature])
            layer.addExpressionField('"value" * 3', QgsField('triple', QVariant.Int))
            plan = LayerPlan(layer.id(), 'dates', 'Dates', pmtiles=False,
                             fields=[FieldPlan(f.name(), f.name()) for f in layer.fields()])
            result = list(snapshot_steps(layer, plan, Path(tmp) / 'dates.gpkg'))[-1]
            copy = QgsVectorLayer(result['path'] + '|layername=dates', 'copy', 'ogr')
            f = next(copy.getFeatures())
            self.assertEqual(f['triple'], 12)
            self.assertEqual(f['day'], QDate(2026, 9, 16))
            self.assertEqual(f['observed'].toUTC(), feature['observed'].toUTC())

    def test_joined_public_field(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            layer = QgsVectorLayer('Point?crs=EPSG:4326&field=key:integer', 'Points', 'memory')
            f = QgsFeature(layer.fields())
            f.setGeometry(QgsGeometry.fromWkt('POINT(139 35)'))
            f.setAttributes([1])
            layer.dataProvider().addFeatures([f])
            table = QgsVectorLayer('None?field=key:integer&field=name:string', 'Names', 'memory')
            f = QgsFeature(table.fields())
            f.setAttributes([1, '公開名'])
            table.dataProvider().addFeatures([f])
            QgsProject.instance().addMapLayer(table)
            join = QgsVectorLayerJoinInfo()
            join.setJoinLayer(table)
            join.setJoinFieldName('key')
            join.setTargetFieldName('key')
            join.setPrefix('joined_')
            layer.addJoin(join)
            plan = LayerPlan(layer.id(), 'joined', 'Joined', pmtiles=False,
                             fields=[FieldPlan('joined_name', 'name')])
            result = list(snapshot_steps(layer, plan, Path(tmp) / 'joined.gpkg'))[-1]
            copy = QgsVectorLayer(result['path'] + '|layername=joined', 'copy', 'ogr')
            self.assertEqual(next(copy.getFeatures())['name'], '公開名')
            self.assertNotIn('key', copy.fields().names())
            QgsProject.instance().removeMapLayer(table)
