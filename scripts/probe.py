import importlib.util
import json
import sys
import os
from pathlib import Path
handles = []
root = Path(sys.executable).parent.parent
if os.name == 'nt':
    for p in (root / 'bin', root / 'apps/qt5/bin', root / 'apps/qgis-ltr/bin'):
        if p.exists():
            handles.append(os.add_dll_directory(str(p)))
from osgeo import gdal
from qgis.core import QgsApplication, Qgis

app = QgsApplication([], False)
app.initQgis()
print(json.dumps({"python": sys.version, "qgis": Qgis.QGIS_VERSION,
    "gdal": gdal.VersionInfo(), "drivers": {n: bool(gdal.GetDriverByName(n)) for n in ("Parquet", "PMTiles", "GPKG")},
    "modules": {n: bool(importlib.util.find_spec(n)) for n in ("pyarrow", "duckdb", "rashid", "pystac", "jsonschema", "shapely")}}, indent=2))
app.exitQgis()
