"""Bounded-memory Hilbert ordering with a disk-backed SQLite index."""
from pathlib import Path
import sqlite3
from osgeo import ogr

def hilbert(x, y, bits=16):
    distance = 0
    step = 1 << (bits - 1)
    while step:
        rx, ry = bool(x & step), bool(y & step)
        distance += step * step * ((3 * int(rx)) ^ int(ry))
        if not ry:
            if rx:
                x, y = step - 1 - x, step - 1 - y
            x, y = y, x
        step >>= 1
    return distance

def write_geoparquet(source_path, output_path, index_path, cancel):
    source = ogr.Open(str(source_path))
    if source is None:
        raise ValueError('Cannot open snapshot')
    layer = source.GetLayer(0)
    xmin, xmax, ymin, ymax = layer.GetExtent()
    dx, dy = xmax - xmin, ymax - ymin
    index = sqlite3.connect(str(index_path))
    index.execute('PRAGMA cache_size=-8192')
    index.execute('PRAGMA temp_store=FILE')
    index.execute('CREATE TABLE feature_order (feature_id INTEGER PRIMARY KEY, hilbert INTEGER NOT NULL)')
    rows = []
    output = None
    try:
        for feature in layer:
            if cancel():
                raise InterruptedError('Cancelled')
            left, right, bottom, top = feature.GetGeometryRef().GetEnvelope()
            x = max(0, min(65535, round(((left + right) / 2 - xmin) / dx * 65535))) if dx else 0
            y = max(0, min(65535, round(((bottom + top) / 2 - ymin) / dy * 65535))) if dy else 0
            rows.append((feature.GetFID(), hilbert(x, y)))
            if len(rows) == 8192:
                index.executemany('INSERT INTO feature_order VALUES (?, ?)', rows)
                rows.clear()
        index.executemany('INSERT INTO feature_order VALUES (?, ?)', rows)
        index.commit()
        output = ogr.GetDriverByName('Parquet').CreateDataSource(str(output_path))
        target = output.CreateLayer(layer.GetName(), layer.GetSpatialRef(), layer.GetGeomType(), options=[
            'COMPRESSION=ZSTD', 'GEOMETRY_ENCODING=WKB', 'GEOMETRY_NAME=geometry', 'WRITE_COVERING_BBOX=YES',
            'ROW_GROUP_SIZE=100000', 'POLYGON_ORIENTATION=UNMODIFIED'])
        if target is None:
            raise ValueError('Could not create GeoParquet layer')
        for field in layer.schema:
            if target.CreateField(field) != ogr.OGRERR_NONE:
                raise ValueError('Cannot create field: ' + field.GetName())
        for (fid,) in index.execute('SELECT feature_id FROM feature_order ORDER BY hilbert, feature_id'):
            if cancel():
                raise InterruptedError('Cancelled')
            original = layer.GetFeature(fid)
            feature = ogr.Feature(target.GetLayerDefn())
            if feature.SetFrom(original) != ogr.OGRERR_NONE or target.CreateFeature(feature) != ogr.OGRERR_NONE:
                raise ValueError('Cannot write GeoParquet feature')
        target = None
        output = None
    finally:
        output = None
        source = None
        index.close()
