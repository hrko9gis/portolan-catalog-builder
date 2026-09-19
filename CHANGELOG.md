# Changelog

## 0.2.0 — Unreleased

- Keep GeoParquet, optional PMTiles and data integrity checks in the GUI workflow.
- Move detailed rashid validation to a user-managed environment; clearly report it as not run.
- Add offline English/Japanese validation guides to the GUI and generated catalogs.
- Exclude native validator dependencies from the ZIP, including when present in a developer checkout.
- Retain GDAL Parquet/optional PMTiles and PyArrow requirements in the QGIS environment.

## 0.1.0 — Unreleased

- Build Portolan 0.2.0 / STAC 1.1.0 catalogs from supported QGIS vector layers.
- Export GeoParquet and optionally PMTiles, with basic map styles and previews.
- Select public fields and capture current edits, selections and spatial scopes.
- Validate locally using the rashid Python API and check exported data integrity.
- Provide English and Japanese interfaces, documentation and reusable settings.

The standalone package has been tested on Windows x64, QGIS 3.44.13,
Python 3.12 and GDAL 3.13.2. It has not been submitted to or approved by the
official QGIS plugin repository. See [publication status](docs/publishing.md).
