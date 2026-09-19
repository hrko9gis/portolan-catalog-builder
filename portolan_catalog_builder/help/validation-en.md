# Detailed validation

Catalog creation runs basic export checks only. Portolan/STAC conformance and
detailed asset validation have **not been run**. Before publishing or distributing,
have the data owner or publication operator perform the following checks.

## 1. Prepare a separate environment

Do not install validation packages into QGIS's Python environment. On a separate
machine or isolated tool environment with uv installed, use:

```text
uv tool install "rashid==0.1.8"
```

uv installation: https://docs.astral.sh/uv/getting-started/installation/
The initial download requires internet access and compatible Python packages.
Follow uv's PATH instructions if the rashid command is not found. This guide
targets rashid 0.1.8 and Portolan 0.2.0; record actual dependency versions.

## 2. Check the complete catalog

Replace OUTPUT_FOLDER with the folder containing catalog.json. Keep all generated
files and subfolders together. Run this outside QGIS:

```text
rashid check "OUTPUT_FOLDER" --schema --data-scope local
```

To save a machine-readable report, run from a directory outside the catalog:

```text
rashid check "OUTPUT_FOLDER" --schema --data-scope local --json > validation-report.json
```

Fix errors and review warnings, rule IDs and skipped checks. Exit code 0 does not
prove every check ran. Missing dependencies or skipped passes must not be treated
as success. Omitting optional PMTiles may produce a recommendation warning.
Revalidate after any changes to the data or catalog.

## 3. Review the data visually

Check fields, geometry, CRS and coverage in QGIS. If PMTiles was generated, review
the preview at several zoom levels. Tile simplification and clipping mean tile
feature counts need not match GeoParquet counts; use GeoParquet for analysis.

## 4. Check hosting after publication

Replace the example URL with the catalog's actual public base URL:

```text
rashid check "OUTPUT_FOLDER" --schema --data-scope local --live --live-base-url "https://data.example.org/my-catalog/"
```

This makes network requests to test hosting, including HTTP Range and CORS.
Local checks alone do not verify hosting. Keep reports outside the catalog.
The plugin does not import external reports or automatically mark the catalog
as validated; this document records the state at export time.

Reference: https://github.com/portolan-sdi/rashid
