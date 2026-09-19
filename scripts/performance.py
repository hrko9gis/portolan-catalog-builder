"""Synthetic scale checks of the full conversion/validation engine."""
import ctypes
import json
import os
from pathlib import Path
import sys
import time
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
handles = []
qroot = Path(sys.executable).parent.parent
if os.name == 'nt':
    for p in (qroot / 'bin', qroot / 'apps/qt5/bin', qroot / 'apps/qgis-ltr/bin'):
        handles.append(os.add_dll_directory(str(p)))
from qgis.core import QgsApplication
app = QgsApplication([], False)
app.initQgis()
from osgeo import ogr, osr
from portolan_catalog_builder.domain import CatalogPlan, LayerPlan, FieldPlan
from portolan_catalog_builder.engine import BuildTask, start_workspace

results = []
for count in (10000, 100000, 1000000):
    started = time.monotonic()
    output = root / '.test-output' / f'performance-{count}-{time.time_ns()}'
    spec = LayerPlan('synthetic', 'points', 'Synthetic points', 'Deterministic synthetic point grid.', pmtiles=False, thumbnail=False,
                     fields=[FieldPlan('value', 'value')])
    plan = CatalogPlan(title='Performance test', description='Synthetic data for performance testing.', producer='Demo', host='Demo',
                      contact='demo@example.org', license='CC0-1.0', layers=[spec], output=str(output))
    workspace = start_workspace(output)
    path = workspace / 'snapshots/points.gpkg'
    data = ogr.GetDriverByName('GPKG').CreateDataSource(str(path))
    crs = osr.SpatialReference()
    crs.ImportFromEPSG(4326)
    layer = data.CreateLayer('points', crs, ogr.wkbPoint)
    layer.CreateField(ogr.FieldDefn('value', ogr.OFTInteger64))
    layer.CreateField(ogr.FieldDefn('portolan_id', ogr.OFTString))
    layer.StartTransaction()
    for index in range(count):
        # Deliberately permute positions so sorting is necessary.
        n = (index * 7919) % count
        point = ogr.Geometry(ogr.wkbPoint)
        point.AddPoint_2D(-10 + (n % 1000) * .001, 30 + (n // 1000) * .001)
        f = ogr.Feature(layer.GetLayerDefn())
        f.SetGeometry(point)
        f.SetField('value', index)
        f.SetField('portolan_id', str(index + 1))
        layer.CreateFeature(f)
    layer.CommitTransaction()
    layer = None
    data = None
    snapshot_seconds = time.monotonic() - started
    snap = {'count': count, 'bbox': [-10, 30, -9.001, 30 + ((count-1)//1000)*.001], 'skipped': 0, 'repaired': 0,
            'crs': 'EPSG:4326', 'path': str(path)}
    task = BuildTask(plan, workspace, {'synthetic': snap}, {}, lambda *args: None)
    task.message.connect(lambda message: print(message, flush=True))
    ok = task.run()
    report = {'features': count, 'success': ok, 'error': task.error, 'total_seconds': round(time.monotonic() - started, 2),
              'snapshot_seconds': round(snapshot_seconds, 2), 'warnings': task.report.get('warning_count'),
              'output_bytes': sum(p.stat().st_size for p in output.rglob('*') if p.is_file()) if output.exists() else 0,
              'output': str(output)}
    results.append(report)
    print(json.dumps(report), flush=True)
    (root / '.test-output/performance.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    if not ok:
        print(json.dumps(task.report, default=str)[:12000], flush=True)
        raise SystemExit(1)
app.exitQgis()
