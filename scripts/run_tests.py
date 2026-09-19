"""Run with the QGIS Python launcher. No GUI window is opened."""
import os
from pathlib import Path
import sys
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
if os.environ.get('PCB_TEST_PACKAGE'):
    sys.path.insert(0, os.environ['PCB_TEST_PACKAGE'])
handles = []
qgis_root = Path(sys.executable).parent.parent
if os.name == 'nt':
    for directory in (qgis_root / 'bin', qgis_root / 'apps/qt5/bin', qgis_root / 'apps/qgis-ltr/bin'):
        if directory.exists():
            handles.append(os.add_dll_directory(str(directory)))
from qgis.core import QgsApplication
app = QgsApplication([], False)
app.initQgis()
import portolan_catalog_builder
print('Testing package:', portolan_catalog_builder.__file__, flush=True)
if os.environ.get('PCB_TEST_PACKAGE'):
    expected = Path(os.environ['PCB_TEST_PACKAGE']).resolve()
    assert Path(portolan_catalog_builder.__file__).resolve().is_relative_to(expected)
    assert not (expected / 'portolan_catalog_builder/_vendor').exists()
import unittest
suite = unittest.defaultTestLoader.discover(str(root / 'tests'))
result = unittest.TextTestRunner(verbosity=2).run(suite)
app.exitQgis()
sys.exit(not result.wasSuccessful())
