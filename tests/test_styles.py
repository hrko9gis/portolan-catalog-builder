import unittest
from qgis.core import (QgsCategorizedSymbolRenderer, QgsGraduatedSymbolRenderer, QgsRendererCategory,
    QgsRendererRange, QgsFillSymbol, QgsVectorLayer)
from portolan_catalog_builder.domain import LayerPlan, FieldPlan
from portolan_catalog_builder.styles import extract_style

class StyleTests(unittest.TestCase):
    def setUp(self):
        self.layer = QgsVectorLayer('Polygon?crs=EPSG:4326&field=category:string&field=amount:integer', 'Styles', 'memory')
        self.plan = LayerPlan(self.layer.id(), 'styles', 'Styles', fields=[FieldPlan('category', 'kind'), FieldPlan('amount', 'count')])

    def test_category_rename_and_hidden_field(self):
        symbol = QgsFillSymbol.createSimple({'color': '#ff0000'})
        self.layer.setRenderer(QgsCategorizedSymbolRenderer('category', [QgsRendererCategory('garden', symbol, 'Garden')]))
        result = extract_style(self.layer, self.plan)
        self.assertEqual(result[0]['filter'], ['==', ['get', 'kind'], 'garden'])
        self.assertEqual(result[0]['paint']['fill-color'], '#ff0000')
        self.plan.fields[0].include = False
        with self.assertRaises(ValueError):
            extract_style(self.layer, self.plan)
        self.plan.basic_style = True
        self.assertNotIn('filter', extract_style(self.layer, self.plan)[0])

    def test_graduated_boundaries(self):
        a, b = QgsFillSymbol.createSimple({'color': '#0000ff'}), QgsFillSymbol.createSimple({'color': '#ff0000'})
        self.layer.setRenderer(QgsGraduatedSymbolRenderer('amount', [QgsRendererRange(0, 10, a, 'Low'), QgsRendererRange(10, 20, b, 'High')]))
        result = extract_style(self.layer, self.plan)
        self.assertIn(['>=', ['get', 'count'], 0.0], result[0]['filter'])
        self.assertIn(['>', ['get', 'count'], 10.0], result[1]['filter'])
        self.assertIn(['<=', ['get', 'count'], 20.0], result[1]['filter'])
