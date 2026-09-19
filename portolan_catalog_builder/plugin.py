from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from pathlib import Path
from qgis.core import QgsMapLayerType
from .i18n import install, tr

class PortolanPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.translator = install()

    def initGui(self):
        self.action = QAction(QIcon(str(Path(__file__).parent / 'resources/icon.svg')), tr('Create Portolan Catalog…'), self.iface.mainWindow())
        self.action.triggered.connect(self.open)
        self.iface.addPluginToMenu('Portolan Catalog Builder', self.action)
        self.iface.addToolBarIcon(self.action)
        self.layer_action = QAction(tr('Add to Portolan Export'), self.iface.mainWindow())
        self.layer_action.triggered.connect(self.open_active)
        self.iface.addCustomActionForLayerType(self.layer_action, 'Portolan', QgsMapLayerType.VectorLayer, True)

    def open(self):
        if self.dialog is None:
            from .ui import BuilderDialog
            self.dialog = BuilderDialog(self.iface)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def open_active(self):
        self.open()
        if not self.dialog.running:
            self.dialog.add_active_layer()

    def unload(self):
        if self.dialog:
            self.dialog.shutdown()
            self.dialog.close()
            self.dialog.deleteLater()
            self.dialog = None
        self.iface.removePluginMenu('Portolan Catalog Builder', self.action)
        self.iface.removeToolBarIcon(self.action)
        self.iface.removeCustomActionForLayerType(self.layer_action)
        self.action.deleteLater()
        self.layer_action.deleteLater()
        QCoreApplication.removeTranslator(self.translator)
