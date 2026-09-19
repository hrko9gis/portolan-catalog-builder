"""Worker-safe conversion, transactional publication, and official validation."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from osgeo import gdal, ogr
from qgis.core import QgsApplication, QgsTask, Qgis
from qgis.PyQt.QtCore import pyqtSignal
from .catalog import build_catalog
from .basic_checks import check_catalog
from .domain import VERSION, write_json
from .spatial_order import write_geoparquet

gdal.UseExceptions()

def diagnostics():
    return {'QGIS': Qgis.QGIS_VERSION, 'Python': sys.version.split()[0], 'GDAL': gdal.VersionInfo('RELEASE_NAME'),
            'GeoParquet': bool(gdal.GetDriverByName('Parquet')), 'PMTiles': bool(gdal.GetDriverByName('PMTiles')),
            'PyArrow': bool(importlib.util.find_spec('pyarrow')),
            'Profile': 'Portolan 0.2.0', 'Detailed validation': 'External; not run by this plugin'}


def validate_environment(plan):
    info = diagnostics()
    problems = []
    for key in ('GeoParquet', 'PyArrow'):
        if not info[key]:
            problems.append('Required capability unavailable: ' + key)
    if any(x.enabled and x.pmtiles for x in plan.layers) and not info['PMTiles']:
        problems.append('PMTiles driver unavailable; turn off PMTiles or use a supported QGIS distribution')
    return problems

def start_workspace(output):
    destination = Path(output).absolute()
    if destination.exists():
        raise ValueError('Output folder already exists; choose a new folder')
    if destination.with_name(destination.name + '.build-report').exists():
        raise ValueError('Build report folder already exists; choose a new output name')
    destination.parent.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix='.portolan-build-', dir=str(destination.parent)))
    (workspace / 'catalog').mkdir()
    (workspace / 'snapshots').mkdir()
    return workspace

def summarize(path, layer, cancel):
    import pyarrow.parquet as pq
    import pyarrow.types as types
    parquet = pq.ParquetFile(path)
    stats, type_map = {}, {}
    names = [f.name for f in layer.fields if f.include]
    for name in names:
        field = parquet.schema_arrow.field(name)
        type_map[name] = str(field.type)
        stats[name] = {'count': 0, 'null_count': 0}
        if types.is_integer(field.type) or types.is_floating(field.type):
            stats[name].update(min=None, max=None, sum=0)
    for batch in parquet.iter_batches(batch_size=8192, columns=names):
        if cancel():
            raise InterruptedError('Cancelled')
        for name in names:
            item = stats[name]
            values = batch.column(name).to_pylist()
            item['count'] += len(values)
            for value in values:
                if value is None:
                    item['null_count'] += 1
                elif 'sum' in item:
                    item['sum'] += value
                    item['min'] = value if item['min'] is None else min(item['min'], value)
                    item['max'] = value if item['max'] is None else max(item['max'], value)
    return parquet.metadata.num_rows, stats, type_map

def fingerprint(path, names, cancel):
    """Order-independent verification of every public value and full geometry."""
    source = ogr.Open(str(path))
    if source is None:
        raise ValueError('Cannot reopen exported data')
    layer = source.GetLayer(0)
    digest_sum, count = 0, 0
    for feature in layer:
        if cancel():
            raise InterruptedError('Cancelled')
        values = [feature.GetField(name) for name in names]
        payload = json.dumps(values, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
        geometry = feature.GetGeometryRef()
        digest = hashlib.sha256(payload + b'\x00' + bytes(geometry.ExportToIsoWkb())).digest()
        digest_sum = (digest_sum + int.from_bytes(digest, 'big')) % (1 << 256)
        count += 1
    source = None
    return count, f'{digest_sum:064x}'

class BuildTask(QgsTask):
    message = pyqtSignal(str)

    def __init__(self, plan, workspace, snapshots, styles, callback):
        super().__init__('Build Portolan catalog', QgsTask.CanCancel)
        self.plan, self.workspace = plan, Path(workspace)
        self.snapshots, self.styles, self.callback = snapshots, styles, callback
        self.error = ''
        self.report = {'build_status': 'running', 'basic_checks': {'status': 'not_run'},
                       'detailed_validation': {'status': 'not_run', 'reason': 'external_validation_required'},
                       'hosting_validation': {'status': 'not_run'}, 'findings': []}

    def checkpoint(self):
        if self.isCanceled():
            raise InterruptedError('Cancelled')

    def run(self):
        root = self.workspace / 'catalog'
        results = []
        try:
            layers = [x for x in self.plan.layers if x.enabled]
            for index, layer in enumerate(layers):
                self.checkpoint()
                self.message.emit('GeoParquet: ' + layer.title)
                folder = root / layer.id
                folder.mkdir(exist_ok=True)
                snapshot = self.snapshots[layer.layer_id]
                path = folder / (layer.id + '.parquet')
                warnings = []
                def handler(level, number, message):
                    if level >= gdal.CE_Warning:
                        warnings.append(message)
                def progress(value, message, data):
                    return not self.isCanceled()
                gdal.PushErrorHandler(handler)
                try:
                    write_geoparquet(snapshot['path'], path, self.workspace / 'snapshots' / (layer.id + '-order.sqlite'), self.isCanceled)
                    count, stats, type_map = summarize(path, layer, self.isCanceled)
                    if count != snapshot['count']:
                        raise ValueError('GeoParquet feature count differs from the snapshot')
                    names = [f.name for f in layer.fields if f.include] + ['portolan_id']
                    before = fingerprint(snapshot['path'], names, self.isCanceled)
                    after = fingerprint(path, names, self.isCanceled)
                    if before != after:
                        raise ValueError('Exported attributes or geometry differ from the snapshot')
                    snapshot['verified_data_fingerprint'] = after[1]
                    if layer.pmtiles:
                        self.message.emit('PMTiles: ' + layer.title)
                        tile_path = folder / (layer.id + '.pmtiles')
                        maximum = layer.maxzoom
                        if layer.autozoom:
                            import math
                            span = max(snapshot['bbox'][2] - snapshot['bbox'][0], snapshot['bbox'][3] - snapshot['bbox'][1], 0.00001)
                            maximum = max(layer.minzoom, min(16, max(8, int(math.ceil(math.log2(360 / span))) + 4)))
                        output = gdal.VectorTranslate(str(tile_path), snapshot['path'], format='PMTiles',
                            datasetCreationOptions=[f'MINZOOM={layer.minzoom}', f'MAXZOOM={maximum}',
                                f'SIMPLIFICATION={layer.simplification}', 'MAX_FEATURES=200000', 'MAX_SIZE=500000'], callback=progress)
                        if output is None:
                            raise ValueError('PMTiles conversion failed')
                        output = None
                        # Validate the signature and that the tile archive can be reopened.
                        with tile_path.open('rb') as stream:
                            if stream.read(8) != b'PMTiles\x03':
                                raise ValueError('Invalid PMTiles header')
                        check = gdal.OpenEx(str(tile_path), gdal.OF_VECTOR)
                        if check is None or check.GetLayerCount() == 0:
                            raise ValueError('PMTiles contains no readable layers')
                        check = None
                        (folder / 'styles').mkdir()
                        style = {'version': 8, 'name': layer.title,
                            'sources': {'data': {'type': 'vector', 'url': '../' + layer.id + '.pmtiles'}},
                            'layers': self.styles[layer.layer_id]}
                        write_json(folder / 'styles/default.json', style)
                        snapshot['maxzoom'] = maximum
                finally:
                    gdal.PopErrorHandler()
                result = {**snapshot, 'statistics': stats, 'types': type_map, 'warnings': warnings}
                results.append((layer, result))
                self.setProgress(75 * (index + 1) / len(layers))
            self.checkpoint()
            self.message.emit('Catalog and documentation')
            build_catalog(root, self.plan, results)
            self.message.emit('Basic export checks')
            self.report['findings'] = check_catalog(root)
            self.report['error_count'] = len(self.report['findings'])
            self.report['warning_count'] = sum(len(r['warnings']) for _, r in results)
            self.report['basic_checks'] = {'status': 'failed' if self.report['findings'] else 'passed',
                'scope': ['input_snapshot', 'feature_count', 'attributes_and_geometry_fingerprint',
                          'parquet_readback', 'optional_pmtiles_readback', 'json_and_local_references']}
            self.report['environment'] = diagnostics()
            self.report['plugin_version'] = VERSION
            self.report['collections'] = {l.id: r for l, r in results}
            write_json(self.workspace / 'build-report.json', self.report)
            if self.report['basic_checks']['status'] != 'passed':
                raise ValueError('Basic export checks failed. Review the findings.')
            self.checkpoint()
            destination = Path(self.plan.output).absolute()
            if destination.exists():
                raise ValueError('Output folder already exists; choose a new folder')
            # On Windows rename refuses an existing destination, including a race.
            root.rename(destination)
            self.report['output'] = str(destination)
            self.report['build_status'] = 'completed'
            report_dir = destination.with_name(destination.name + '.build-report')
            try:
                report_dir.mkdir()
                self.report['report_folder'] = str(report_dir)
                write_json(report_dir / 'build-report.json', self.report)
                shutil.copyfile(Path(__file__).parent / 'profiles/profile.json', report_dir / 'profile.json')
            except OSError as exc:
                # Data has been finalized. Never misreport a successful export as missing.
                self.report['report_copy_warning'] = str(exc)
            write_json(self.workspace / 'build-report.json', self.report)
            self.setProgress(100)
            return True
        except Exception as exc:
            self.error = str(exc)
            self.report['build_status'] = 'cancelled' if isinstance(exc, InterruptedError) else 'failed'
            if self.report['basic_checks']['status'] == 'not_run':
                self.report['basic_checks']['status'] = 'incomplete'
            self.report['error'] = self.error
            write_json(self.workspace / 'build-report.json', self.report)
            return False

    def finished(self, success):
        self.callback(success, self.error, self.report, self.workspace)
