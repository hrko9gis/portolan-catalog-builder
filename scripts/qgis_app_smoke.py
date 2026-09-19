"""Run using QGIS --code in a disposable profile populated from the release ZIP."""
import json
import hashlib
import os
from pathlib import Path
import traceback
import sys
from qgis.core import QgsApplication, Qgis
from qgis.PyQt.QtCore import QTimer
import qgis.utils


def verify():
    result = {'qgis': Qgis.QGIS_VERSION, 'pid': os.getpid(),
              'profile': QgsApplication.qgisSettingsDirPath(), 'passed': False}
    try:
        name = 'portolan_catalog_builder'
        assert qgis.utils.iface is not None, 'Actual QGIS interface unavailable'
        if os.environ.get('PCB_INSTALL_ZIP'):
            profile = Path(QgsApplication.qgisSettingsDirPath()).resolve()
            archive = Path(os.environ['PCB_INSTALL_ZIP']).resolve()
            workspace = archive.parents[1] / '.test-output'
            assert profile.is_relative_to(workspace.resolve()), 'Only disposable workspace profiles are allowed'
            plugin_root = profile / 'python/plugins'
            # --code inherits the launch working directory; prevent source fallback.
            sys.path = [str(plugin_root)] + [p for p in sys.path
                         if p and Path(p).resolve() != workspace.parent.resolve()]
            result['zip_sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
            import pyplugin_installer
            assert pyplugin_installer.instance().installFromZipFile(str(archive)), 'QGIS ZIP installer failed'
            result['installed_via_qgis_zip_installer'] = True
        if not qgis.utils.isPluginLoaded(name):
            assert qgis.utils.loadPlugin(name), 'Plugin import failed'
            assert qgis.utils.startPlugin(name), 'Plugin activation failed'
        import portolan_catalog_builder
        result['loaded_from'] = portolan_catalog_builder.__file__
        if os.environ.get('PCB_INSTALL_ZIP'):
            assert Path(portolan_catalog_builder.__file__).resolve().is_relative_to(plugin_root.resolve()), 'Loaded checkout instead of installed ZIP'
            assert not (plugin_root / name / '_vendor').exists()
        plugin = qgis.utils.plugins[name]
        plugin.action.trigger()
        assert plugin.dialog is not None and plugin.dialog.isVisible()
        assert plugin.dialog.tabs.count() == 6
        plugin.dialog.open_validation_guide()
        assert plugin.dialog.guide_dialog.isVisible()
        plugin.dialog.guide_dialog.close()
        assert qgis.utils.unloadPlugin(name), 'Plugin unload failed'
        result['passed'] = True
    except Exception:
        result['error'] = traceback.format_exc()
    finally:
        Path(os.environ['PCB_APP_SMOKE_REPORT']).write_text(json.dumps(result, indent=2), encoding='utf-8')
        QgsApplication.instance().quit()


QTimer.singleShot(1500, verify)
