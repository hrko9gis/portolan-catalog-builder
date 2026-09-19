"""Main-thread, incremental snapshots of live QGIS layers."""
from pathlib import Path
import math
from qgis.PyQt.QtCore import QVariant, QSize
from qgis.PyQt.QtGui import QColor
from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeature,
    QgsFeatureRequest, QgsField, QgsFields, QgsGeometry, QgsMapSettings, QgsExpression,
    QgsMapRendererParallelJob, QgsProject, QgsRectangle, QgsVectorFileWriter,
    QgsVectorLayer, QgsWkbTypes)
from .styles import extract_style

ALLOWED = (QVariant.String, QVariant.Int, QVariant.LongLong, QVariant.Double, QVariant.Bool, QVariant.Date, QVariant.DateTime)

def check_layer(layer):
    if not isinstance(layer, QgsVectorLayer) or not layer.isValid():
        return 'Only valid vector layers are supported'
    if layer.providerType() not in ('ogr', 'memory'):
        return 'Only local OGR and memory layers are supported in this release'
    if layer.providerType() == 'ogr' and not Path(layer.source().split('|')[0]).is_file():
        return 'The source must be a local file'
    wkb = layer.wkbType()
    if QgsWkbTypes.hasZ(wkb) or QgsWkbTypes.hasM(wkb) or QgsWkbTypes.isCurvedType(wkb):
        return 'Only 2D linear geometry is supported'
    if QgsWkbTypes.flatType(wkb) not in (QgsWkbTypes.Point, QgsWkbTypes.MultiPoint,
            QgsWkbTypes.LineString, QgsWkbTypes.MultiLineString, QgsWkbTypes.Polygon, QgsWkbTypes.MultiPolygon):
        return 'Mixed or unsupported geometry type'
    if not layer.crs().isValid():
        return 'Define the layer CRS first'
    return ''

def snapshot_steps(layer, plan, path, cancelled=lambda: False):
    """Yield after bounded batches; called exclusively by a GUI-thread QTimer."""
    issue = check_layer(layer)
    if issue:
        raise ValueError(issue)
    fields = QgsFields()
    chosen = [f for f in plan.fields if f.include]
    indices = []
    expressions = {}
    expression_context = layer.createExpressionContext()
    for item in chosen:
        index = layer.fields().indexFromName(item.source)
        if index < 0 or layer.fields()[index].type() not in ALLOWED:
            raise ValueError(f'Unsupported or missing field: {item.source}')
        field = QgsField(layer.fields()[index])
        field.setName(item.name)
        fields.append(field)
        indices.append(index)
        if layer.fields().fieldOrigin(index) == QgsFields.OriginExpression:
            expression = QgsExpression(layer.expressionField(index))
            if expression.hasParserError() or not expression.prepare(expression_context):
                raise ValueError('Cannot prepare calculated field: ' + item.source)
            expressions[index] = expression
    fields.append(QgsField('portolan_id', QVariant.String))
    crs = QgsCoordinateReferenceSystem(plan.output_crs) if plan.output_crs else layer.crs()
    if not crs.isValid():
        raise ValueError('Invalid output CRS')
    context = QgsProject.instance().transformContext()
    transform = QgsCoordinateTransform(layer.crs(), crs, context)
    bbox_transform = QgsCoordinateTransform(crs, QgsCoordinateReferenceSystem('EPSG:4326'), context)
    clip = None
    request = QgsFeatureRequest()
    if plan.scope == 'selected':
        ids = layer.selectedFeatureIds()
        if not ids:
            raise ValueError('Select at least one feature')
        request.setFilterFids(ids)
    if plan.scope in ('extent', 'clip'):
        clip = QgsGeometry.fromRect(QgsRectangle(*plan.extent))
        # Densify the rectangle before reprojection to preserve curved edges.
        clip = clip.densifyByCount(32)
        clip.transform(QgsCoordinateTransform(QgsCoordinateReferenceSystem(plan.extent_crs), layer.crs(), context))
        request.setFilterRect(clip.boundingBox())
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = 'GPKG'
    options.layerName = plan.id
    options.fileEncoding = 'UTF-8'
    options.layerOptions = ['FID=fid', 'GEOMETRY_NAME=geom']
    writer = QgsVectorFileWriter.create(str(path), fields, QgsWkbTypes.multiType(layer.wkbType()), crs, context, options)
    if writer.hasError() != QgsVectorFileWriter.NoError:
        raise ValueError(writer.errorMessage())
    changed = [False]
    signals = [layer.featureAdded, layer.featureDeleted, layer.geometryChanged, layer.attributeValueChanged,
               layer.updatedFields, layer.subsetStringChanged, layer.willBeDeleted]
    def mark(*args):
        changed[0] = True
    for signal in signals:
        signal.connect(mark)
    count = skipped = repaired = visited = 0
    bounds = None
    try:
        for original in layer.getFeatures(request):
            if cancelled():
                raise InterruptedError('Cancelled')
            if changed[0]:
                raise ValueError('The input layer changed during the snapshot; retry')
            visited += 1
            if visited % 300 == 0:
                yield {'visited': visited}
            geom = QgsGeometry(original.geometry())
            if geom.isNull() or geom.isEmpty():
                if plan.skip_empty:
                    skipped += 1
                    continue
                raise ValueError(f'Empty geometry at feature {original.id()}')
            if not geom.isGeosValid():
                if not plan.repair:
                    raise ValueError(f'Invalid geometry at feature {original.id()}')
                geom = geom.makeValid()
                repaired += 1
            if clip:
                if not geom.intersects(clip):
                    continue
                if plan.scope == 'clip':
                    geom = geom.intersection(clip)
            if geom.isEmpty() or geom.isNull():
                skipped += 1
                continue
            if QgsWkbTypes.geometryType(geom.wkbType()) != layer.geometryType():
                raise ValueError('Clipping or repair changed the geometry type')
            geom.transform(transform)
            geom.convertToMultiType()
            geo = QgsGeometry(geom)
            geo.transform(bbox_transform)
            bbox = geo.boundingBox()
            values = [bbox.xMinimum(), bbox.yMinimum(), bbox.xMaximum(), bbox.yMaximum()]
            if not all(math.isfinite(v) for v in values) or not (-180 <= values[0] <= values[2] <= 180 and -90 <= values[1] <= values[3] <= 90):
                raise ValueError('Invalid WGS84 extent')
            if bbox.width() > 180:
                raise ValueError('Antimeridian-crossing data is not supported yet')
            if plan.pmtiles and (values[1] < -85.05112878 or values[3] > 85.05112878):
                raise ValueError('Outside Web Mercator bounds; turn off PMTiles')
            if bounds is None:
                bounds = values
            else:
                bounds = [min(bounds[0], values[0]), min(bounds[1], values[1]), max(bounds[2], values[2]), max(bounds[3], values[3])]
            out = QgsFeature(fields)
            out.setGeometry(geom)
            values = []
            expression_context.setFeature(original)
            for i in indices:
                if i in expressions:
                    value = expressions[i].evaluate(expression_context)
                    if expressions[i].hasEvalError():
                        raise ValueError('Calculated field failed: ' + layer.fields()[i].name())
                else:
                    value = original.attribute(i)
                values.append(value)
            out.setAttributes(values + [str(count + 1)])
            if not writer.addFeature(out):
                raise ValueError(writer.lastError())
            count += 1
        if not count:
            raise ValueError('The output collection would be empty')
        if changed[0]:
            raise ValueError('The input layer changed during the snapshot; retry')
        if bounds[2] - bounds[0] > 180:
            raise ValueError('Antimeridian or very wide extent is not supported yet')
    finally:
        for signal in signals:
            try:
                signal.disconnect(mark)
            except (TypeError, RuntimeError):
                pass
        del writer
    yield {'complete': True, 'count': count, 'skipped': skipped, 'repaired': repaired,
           'bbox': bounds, 'crs': crs.authid() or crs.toWkt(), 'path': str(path)}

def thumbnail(layer, plan, snapshot, path, parent):
    """Async render job using the snapshot, never a basemap or private columns."""
    clone = QgsVectorLayer(str(snapshot) + '|layername=' + plan.id, plan.title, 'ogr')
    if not clone.isValid():
        raise ValueError('Cannot load snapshot for thumbnail')
    # Classification fields may have been renamed.
    renderer = layer.renderer().clone()
    if renderer.type() in ('categorizedSymbol', 'graduatedSymbol'):
        name = next((f.name for f in plan.fields if f.source == renderer.classAttribute() and f.include), None)
        if name:
            renderer.setClassAttribute(name)
        else:
            renderer = None
    if renderer and not plan.basic_style:
        clone.setRenderer(renderer)
    clone.setOpacity(layer.opacity())
    settings = QgsMapSettings()
    settings.setLayers([clone])
    settings.setDestinationCrs(clone.crs())
    extent = clone.extent()
    if extent.width() == 0 or extent.height() == 0:
        extent.grow(0.01 if clone.crs().isGeographic() else 100)
    extent.scale(1.15)
    settings.setExtent(extent)
    settings.setOutputSize(QSize(640, 400))
    settings.setBackgroundColor(QColor('white'))
    job = QgsMapRendererParallelJob(settings)
    return job, clone
