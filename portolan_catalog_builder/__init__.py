"""QGIS entry point. Import QGIS only when the plugin is activated."""

def classFactory(iface):
    from .plugin import PortolanPlugin
    return PortolanPlugin(iface)

