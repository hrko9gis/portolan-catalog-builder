# Third-party software

Portolan Catalog Builder's own code is licensed under **GPL-3.0-or-later**.
See [LICENSE](LICENSE). This does not replace the licenses of dependencies.

## Runtime supplied by QGIS

QGIS, Qt/PyQt, GDAL/OGR and PyArrow are used through their Python APIs. They are
provided by the QGIS environment and are not copied from that installation into
the plugin package. Their respective upstream licenses apply.

## External validator

Version 0.2.0 does not distribute rashid or its native dependency tree. The
historical `requirements-runtime.lock` is retained for developer reference only.
Users install the external validator independently, under its upstream licenses.
The legacy worker helper and local `_vendor` directory are excluded from the ZIP.

## Browser preview

| Dependency | Version | License | Upstream source |
| --- | --- | --- | --- |
| MapLibre GL JS | 5.6.2 | BSD-3-Clause | https://github.com/maplibre/maplibre-gl-js |
| PMTiles JavaScript | 4.3.0 | BSD-3-Clause | https://github.com/protomaps/PMTiles |

The build downloader retrieves the JavaScript/CSS and accompanying upstream
licenses into `portolan_catalog_builder/preview/vendor/`. The distribution must
retain `MAPLIBRE-LICENSE.txt` and `PMTILES-LICENSE.txt`. SHA-256 values are recorded
in `profiles/runtime-lock.json`. These are local assets; the map viewer does not
load them from a public CDN at runtime.
