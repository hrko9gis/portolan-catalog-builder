# Contributing

Please use [GitHub Issues](https://github.com/hrko9gis/portolan-catalog-builder/issues) for reproducible bug reports and feature
requests. Include the plugin, QGIS, Python and GDAL versions, operating system,
steps to reproduce, and expected and actual results. Remove private paths,
credentials and sensitive GIS data before sharing logs or build reports.

The plugin is experimental. Supported capabilities and known restrictions are
documented in [README](README.md) and [implementation notes](docs/implementation-status.md).

## Development

1. Clone this repository and use a QGIS installation with the Parquet and
   PMTiles GDAL drivers and PyArrow. The tested environment is listed in README.
2. Follow [BUILDING.md](BUILDING.md) to prepare preview libraries. The validator
   is external and is not required to build or use the plugin.
3. Run `python-qgis-ltr.bat scripts/run_tests.py` using the QGIS Python launcher.
4. For changes to exports or the wizard, also run `scripts/gui_smoke.py` with that
   launcher. For preview changes, run `scripts/browser_smoke.py` with Playwright
   and Edge available in the development environment.
5. Update documentation and CHANGELOG when behavior changes. Keep user-facing
   English text translatable and update `portolan_catalog_builder/i18n/ja.json`.
   Run `scripts/translations.py <path-to-lrelease>` to regenerate TS/QM files.

Keep source data unchanged. Use small synthetic fixtures for tests. Do not commit
generated catalogs, validation snapshots, dependencies, credentials or ZIP files.
Plugin code and contributions are licensed under GPL-3.0-or-later; preserve all
third-party notices.
