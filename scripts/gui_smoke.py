"""Exercise the real dialog, event loop, tasks and result view without opening a window."""
import os
from pathlib import Path
import sys
import time
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'tests'))
if len(sys.argv) > 1:
    sys.path.insert(0, sys.argv[1])
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
handles = []
qroot = Path(sys.executable).parent.parent
if os.name == 'nt':
    for p in (qroot / 'bin', qroot / 'apps/qt5/bin', qroot / 'apps/qgis-ltr/bin'):
        handles.append(os.add_dll_directory(str(p)))
from qgis.core import QgsApplication, QgsProject
app = QgsApplication([], True)
app.initQgis()
from qgis.PyQt.QtGui import QFontDatabase, QFont
font_id = QFontDatabase.addApplicationFont('C:/Windows/Fonts/meiryo.ttc')
if font_id >= 0:
    app.setFont(QFont(QFontDatabase.applicationFontFamilies(font_id)[0], 9))
print('Offscreen font:', font_id, app.font().family(), flush=True)
from test_ui import FakeIface
from test_build import BuildTests
from portolan_catalog_builder.ui import BuilderDialog
from portolan_catalog_builder.i18n import install

locale = sys.argv[2] if len(sys.argv) > 2 else 'ja'
QgsApplication.setTranslation(locale)
translator = install()
import portolan_catalog_builder
print('Testing package:', portolan_catalog_builder.__file__, flush=True)
if len(sys.argv) > 1:
    assert Path(portolan_catalog_builder.__file__).resolve().is_relative_to(Path(sys.argv[1]).resolve())
    assert not (Path(sys.argv[1]) / 'portolan_catalog_builder/_vendor').exists()
layer = BuildTests().make_layer()
QgsProject.instance().addMapLayer(layer)
dialog = BuilderDialog(FakeIface())
dialog.error = lambda error: (_ for _ in ()).throw(RuntimeError(str(error)))
for key, value in {'id': 'parks-demo', 'title': 'Parks Demo', 'description': 'Fictional parks for GUI testing.',
                   'producer': 'Demo', 'host': 'Demo', 'contact': 'demo@example.org', 'license': 'CC0-1.0'}.items():
    obj = dialog.catalog_inputs[key]
    obj.setPlainText(value) if hasattr(obj, 'setPlainText') else obj.setText(value)
dialog.layer_inputs['description'].setText('Two fictional parks in the west area.')
dialog.save_layer()
output = root / '.test-output' / ('gui-' + str(time.time_ns()))
dialog.destination.setText(str(output))
dialog.tabs.setCurrentIndex(4)
dialog.start_build()
deadline = time.monotonic() + 120
while dialog.running and time.monotonic() < deadline:
    app.processEvents()
    time.sleep(0.005)
assert not dialog.running, 'GUI build timed out'
assert output.joinpath('catalog.json').is_file(), dialog.log.toPlainText()
assert dialog.result_report['basic_checks']['status'] == 'passed', dialog.result_report
assert output.joinpath('parks/thumbnail.png').is_file()
assert dialog.attributes.rowCount() == 2
assert dialog.result_report['detailed_validation']['status'] == 'not_run'
assert dialog.result_report['hosting_validation']['status'] == 'not_run'
assert 'passed' not in dialog.result_report
assert ('未実施' if locale == 'ja' else 'has not been run') in dialog.result_status.text()
dialog.open_validation_guide()
from qgis.PyQt.QtWidgets import QTextBrowser
guide = dialog.guide_dialog.findChild(QTextBrowser).toPlainText()
assert ('詳細検証の手順' if locale == 'ja' else 'Detailed validation') in guide
assert 'rashid check' in guide
dialog.guide_dialog.close()
dialog.tabs.setCurrentIndex(5)
dialog.resize(1120, 780)
dialog.show()
for _ in range(20):
    app.processEvents()
dialog.grab().save(str(root / '.test-output/gui-result.png'))
dialog.grab().save(str(root / f'.test-output/gui-result-{locale}.png'))
print('GUI build passed:', output)
print('Basic checks:', dialog.result_report['error_count'], 'errors,', dialog.result_report['warning_count'], 'warnings')
print('Settings language:', dialog.tabs.tabText(0))
print('Result status:', dialog.result_status.text())
dialog.shutdown()
dialog.close()
from qgis.PyQt import sip
dialog.canvas.setLayers([])
dialog.canvas_layer = None
sip.delete(dialog)
QgsProject.instance().clear()
app.exitQgis()
