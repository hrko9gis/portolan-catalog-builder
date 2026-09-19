import unittest
from qgis.core import QgsApplication, QgsProject
from qgis.gui import QgsMapCanvas
from qgis.PyQt.QtWidgets import QMainWindow
from portolan_catalog_builder.ui import BuilderDialog
import test_build

class FakeIface:
    def __init__(self):
        self.window = QMainWindow()
        self.canvas = QgsMapCanvas()
    def mainWindow(self):
        return self.window
    def mapCanvas(self):
        return self.canvas

class UiTests(unittest.TestCase):
    def test_dialog_and_settings(self):
        layer = test_build.BuildTests().make_layer()
        QgsProject.instance().addMapLayer(layer)
        dialog = BuilderDialog(FakeIface())
        self.assertEqual(dialog.tabs.count(), 6)
        self.assertEqual(dialog.plan.layers[0].id, 'parks')
        self.assertTrue(dialog.plan.layers[0].pmtiles)
        dialog.tiles_enabled.setChecked(False)
        self.assertFalse(dialog.collect().layers[0].pmtiles)
        self.assertFalse(dialog.tile_controls.isEnabled())
        dialog.all_tiles.setCheckState(2)
        dialog.toggle_all_tiles()
        self.assertTrue(dialog.collect().layers[0].pmtiles)
        dialog.all_tiles.setCheckState(0)
        dialog.toggle_all_tiles()
        self.assertFalse(dialog.collect().layers[0].pmtiles)
        dialog.open_validation_guide()
        self.assertTrue(dialog.guide_dialog.isVisible())
        dialog.guide_dialog.close()
        dialog.shutdown()
        dialog.close()
        QgsProject.instance().clear()
