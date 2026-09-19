"""Serializable plans and input validation, independent of QGIS."""
from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

VERSION = '0.2.0'
PROFILE = 'https://schemas.portolan-sdi.org/portolan/v0.2.0/schema.json'
SETTINGS_VERSION = 1

@dataclass
class FieldPlan:
    source: str
    name: str
    type: str = ''
    include: bool = True
    title: str = ''
    description: str = ''
    unit: str = ''
    null_meaning: str = ''
    codes: str = ''

@dataclass
class LayerPlan:
    layer_id: str
    id: str
    title: str
    description: str = ''
    enabled: bool = True
    pmtiles: bool = True
    thumbnail: bool = True
    scope: str = 'all'
    extent: list = field(default_factory=list)
    extent_crs: str = ''
    output_crs: str = ''
    repair: bool = False
    skip_empty: bool = False
    minzoom: int = 0
    maxzoom: int = 14
    autozoom: bool = True
    simplification: float = 1.0
    basic_style: bool = False
    fields: list[FieldPlan] = field(default_factory=list)
    producer: str = ''
    host: str = ''
    contact: str = ''
    license: str = ''
    license_url: str = ''
    source_url: str = ''
    canonical_url: str = ''
    start: str = ''
    end: str = ''
    notes: str = ''
    keywords: str = ''

@dataclass
class CatalogPlan:
    id: str = 'my-catalog'
    title: str = ''
    description: str = ''
    producer: str = ''
    host: str = ''
    contact: str = ''
    license: str = ''
    license_url: str = ''
    source_url: str = ''
    canonical_url: str = ''
    keywords: str = ''
    notes: str = ''
    document_language: str = 'en'
    output: str = ''
    layers: list[LayerPlan] = field(default_factory=list)
    settings_schema_version: int = SETTINGS_VERSION

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        if data.get('settings_schema_version') != SETTINGS_VERSION:
            raise ValueError('Unsupported settings version')
        data = dict(data)
        data['layers'] = [LayerPlan(**{**item, 'fields': [FieldPlan(**f) for f in item['fields']]})
                          for item in data.get('layers', [])]
        return cls(**data)

def valid_id(value):
    reserved = {'con', 'prn', 'aux', 'nul'} | {f'{s}{n}' for s in ('com', 'lpt') for n in range(1, 10)}
    return bool(re.fullmatch('[a-z][a-z0-9_-]*', value)) and value not in reserved

def slug(name, index):
    value = re.sub('[^a-z0-9_-]+', '-', name.lower()).strip('-')
    return value if valid_id(value) else f'layer-{index:02d}'

def inherited(plan, layer, key):
    return getattr(layer, key, '') or getattr(plan, key, '')

def safe_url(value):
    parsed = urlsplit(value)
    return parsed.scheme == 'https' and bool(parsed.netloc) and not parsed.username and not parsed.password

def validate_plan(plan):
    errors = []
    if not valid_id(plan.id):
        errors.append('Invalid catalog ID')
    for key in ('title', 'description', 'producer', 'host', 'contact', 'license'):
        if not getattr(plan, key).strip():
            errors.append(f'Missing catalog field: {key}')
    if not plan.output:
        errors.append('Choose an output folder')
    elif Path(plan.output).exists():
        errors.append('Output folder already exists; choose a new folder')
    layers = [item for item in plan.layers if item.enabled]
    if not layers:
        errors.append('Select at least one layer')
    ids = set()
    for layer in layers:
        prefix = layer.title + ': '
        if not valid_id(layer.id) or layer.id in ids:
            errors.append(prefix + 'Invalid or duplicate collection ID')
        ids.add(layer.id)
        if not layer.title.strip() or not layer.description.strip():
            errors.append(prefix + 'Title and description are required')
        if layer.scope not in ('all', 'selected', 'extent', 'clip'):
            errors.append(prefix + 'Unknown selection scope')
        if layer.scope in ('extent', 'clip') and (len(layer.extent) != 4 or not layer.extent_crs):
            errors.append(prefix + 'Capture a map extent first')
        names = [f.name for f in layer.fields if f.include]
        if len({n.casefold() for n in names}) != len(names) or any(not n.strip() for n in names):
            errors.append(prefix + 'Output field names must be unique and non-empty')
        if any(n.casefold() in ('fid', 'geom', 'geometry', 'bbox', 'geometry_bbox', 'portolan_id') for n in names):
            errors.append(prefix + 'Reserved output field name: fid, geom, geometry, bbox, geometry_bbox, portolan_id')
        if layer.pmtiles and (not 0 <= layer.minzoom <= 22 or (not layer.autozoom and not layer.minzoom <= layer.maxzoom <= 22)):
            errors.append(prefix + 'Zoom levels must satisfy 0 <= minimum <= maximum <= 22')
        contact = inherited(plan, layer, 'contact')
        if not (safe_url(contact) or re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', contact)):
            errors.append(prefix + 'Contact must be an HTTPS URL or email address')
        if inherited(plan, layer, 'license') == 'other' and not inherited(plan, layer, 'license_url'):
            errors.append(prefix + 'Provide a license URL for other')
        if inherited(plan, layer, 'producer') != inherited(plan, layer, 'host') and not inherited(plan, layer, 'source_url'):
            errors.append(prefix + 'A mirrored collection requires a source URL')
        for key in ('source_url', 'canonical_url', 'license_url'):
            value = inherited(plan, layer, key)
            if value and not safe_url(value):
                errors.append(prefix + f'{key} must be an HTTPS URL without credentials')
        dates = []
        for value in (layer.start, layer.end):
            if value:
                try:
                    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    if date.tzinfo is None:
                        raise ValueError()
                    dates.append(date)
                except ValueError:
                    errors.append(prefix + 'Dates must use ISO 8601 with a time zone')
        if len(dates) == 2 and dates[0] > dates[1]:
            errors.append(prefix + 'Start date must not follow end date')
    return errors

def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
