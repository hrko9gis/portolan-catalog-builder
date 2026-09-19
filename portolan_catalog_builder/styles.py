"""Translate supported QGIS symbols into portable MapLibre paint."""
from qgis.core import QgsWkbTypes, QgsUnitTypes

def _paint(symbol, geometry_type):
    if symbol.symbolLayerCount() != 1 or symbol.symbolLayer(0).dataDefinedProperties().hasActiveProperties():
        raise ValueError('Complex or data-defined symbols require a basic style')
    part = symbol.symbolLayer(0)
    properties = part.properties()
    expected = {0: 'SimpleMarker', 1: 'SimpleLine', 2: 'SimpleFill'}[geometry_type]
    if part.layerType() != expected:
        raise ValueError('Unsupported symbol; choose a basic style')
    if symbol.dataDefinedProperties().hasActiveProperties():
        raise ValueError('Data-defined symbols require a basic style')
    color = symbol.color().name()
    opacity = symbol.opacity() * symbol.color().alphaF()
    def pixels(value, unit):
        if unit == QgsUnitTypes.RenderMillimeters:
            return value * 96 / 25.4
        if unit == QgsUnitTypes.RenderPixels:
            return value
        if unit == QgsUnitTypes.RenderPoints:
            return value * 96 / 72
        raise ValueError('Map-unit symbols require a basic style')
    if geometry_type == 0:
        if properties.get('name') != 'circle':
            raise ValueError('Only circle markers are supported; choose a basic style')
        return 'circle', {'circle-color': color, 'circle-opacity': opacity,
                          'circle-radius': pixels(symbol.size(), symbol.sizeUnit()) / 2,
                          'circle-stroke-color': part.strokeColor().name(),
                          'circle-stroke-width': pixels(part.strokeWidth(), part.strokeWidthUnit()),
                          'circle-stroke-opacity': symbol.opacity() * part.strokeColor().alphaF()}
    if geometry_type == 1:
        if properties.get('line_style', 'solid') != 'solid' or properties.get('use_custom_dash', '0') != '0':
            raise ValueError('Dashed lines require a basic style')
        return 'line', {'line-color': color, 'line-opacity': opacity,
                        'line-width': pixels(symbol.width(), symbol.widthUnit())}
    return 'fill', {'fill-color': color, 'fill-opacity': opacity,
                    'fill-outline-color': part.strokeColor().name()}

def extract_style(layer, plan):
    kind = QgsWkbTypes.geometryType(layer.wkbType())
    if plan.basic_style:
        type_ = {0: 'circle', 1: 'line', 2: 'fill'}[kind]
        paint = {type_ + '-color': '#2878a0', type_ + '-opacity': 0.75}
        if kind == 0:
            paint['circle-radius'] = 5
        if kind == 1:
            paint['line-width'] = 2
        return [{'id': 'data', 'type': type_, 'source': 'data', 'source-layer': plan.id, 'paint': paint}]
    renderer = layer.renderer()
    if layer.labelsEnabled():
        raise ValueError('Labels are not supported yet; choose a basic style')
    out = []
    def append(symbol, filter_=None):
        type_, paint = _paint(symbol, kind)
        paint[type_ + '-opacity'] *= layer.opacity()
        entry = {'id': f'layer-{len(out)}', 'type': type_, 'source': 'data', 'source-layer': plan.id, 'paint': paint}
        if filter_ is not None:
            entry['filter'] = filter_
        out.append(entry)
    if renderer.type() == 'singleSymbol':
        append(renderer.symbol())
    elif renderer.type() in ('categorizedSymbol', 'graduatedSymbol'):
        column = renderer.classAttribute()
        name = next((f.name for f in plan.fields if f.source == column and f.include), None)
        if name is None:
            raise ValueError('Publish the classification field or choose a basic style')
        if renderer.type() == 'categorizedSymbol':
            for cat in renderer.categories():
                if not cat.renderState():
                    continue
                value = cat.value()
                if value is None or value == '':
                    # QGIS uses the empty category as an unmatched/default category.
                    values = [c.value() for c in renderer.categories() if c.value() not in (None, '')]
                    append(cat.symbol(), ['!', ['in', ['get', name], ['literal', values]]])
                elif isinstance(value, (str, int, float, bool)):
                    append(cat.symbol(), ['==', ['get', name], value])
                else:
                    raise ValueError('Unsupported category value; choose a basic style')
        else:
            for index, item in enumerate(renderer.ranges()):
                if item.renderState():
                    append(item.symbol(), ['all', ['has', name], ['!=', ['get', name], None],
                        ['>=' if index == 0 else '>', ['get', name], item.lowerValue()],
                        ['<=', ['get', name], item.upperValue()]])
    else:
        raise ValueError('Unsupported renderer; choose a basic style')
    if not out:
        raise ValueError('The style has no visible symbols')
    return out
