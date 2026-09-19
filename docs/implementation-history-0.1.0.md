# Historical record: version 0.1.0 only

Do not use this file to assess the current package. See [current status](implementation-status.md).

# Implementation and validation notes

Initial implementation: **0.1.0**, experimental. Last reviewed: 2026-09-16.

Official repository submission is **not ready**: the standalone ZIP contains
native binaries and exceeds the official size limit. Source publication and
metadata preparation do not resolve this distribution issue. See
[publication status](publishing.md) for requirements and remaining work.

## Implemented scope

The six-page QGIS workflow implements the design's initial vector release: layer selection, scoped snapshots including current edits and evaluated attributes, public-field selection, GeoParquet, optional per-layer PMTiles, basic MapLibre styles, thumbnails, STAC, documentation, official local validation, result previews and reusable settings.

The GUI is English-first, with a compiled Qt Japanese translation selected from QGIS's effective translation language. Documentation templates independently support English and Japanese. The runtime does not invoke Portolan CLI, ogr2ogr, Tippecanoe, pip or npm.

## Decisions made during implementation

| Design question | Implemented decision |
|---|---|
| First supported package | Windows x64, QGIS 3.44.13 / Python 3.12 / GDAL 3.13.2 |
| GeoParquet spatial sorting | Explicit 16-bit Hilbert ordering, disk-backed SQLite index, bounded 8,192-entry batches |
| Why not only GDAL SORT_BY_BBOX? | A shuffled 10,000-point fixture failed rashid's row-locality test with that option; explicit ordering passed |
| GeoParquet writing | GDAL/OGR API, GeoParquet 1.1, WKB, ZSTD, 100,000-row groups, covering statistics |
| Data preservation | Count and order-independent SHA-256-based fingerprints of all public values plus complete geometries |
| Official validator | Fixed rashid 0.1.8 Python API; Windows/Python 3.12 dependencies bundled in an isolated worker process |
| Metadata profile | Portolan 0.2.0, STAC 1.1.0; packaged schemas used offline |
| Web preview | Bundled MapLibre 5.6.2 and PMTiles 4.3.0 served to the default browser over loopback |
| Embedded WebEngine | Browser fallback selected for this package; no embedded WebEngine dependency |
| Rebuild safety | New output folder only; no merging or replacement of an existing catalog |
| Reports | Sibling `<output>.build-report` plus diagnostic staging directory |
| Temporary data cleanup | Retained for diagnostics; remove after review when QGIS releases open handles |

The pre-release dependency artifacts used for the shipped profile are inventoried in `portolan_catalog_builder/profiles/runtime-lock.json`; all installed Python versions are pinned in `requirements-runtime.lock`.

## Automated checks

The test suite currently covers:

- Mixed PMTiles settings, complete omission when disabled, mandatory GeoParquet output, metadata links and official validation.
- Private attributes absent from GeoParquet and documentation inputs; public attribute renaming.
- 64-bit integers above JavaScript's safe-integer range, leading-zero codes, booleans and nulls.
- Current edit-buffer values, selected features, clipping and cancellation.
- Rejection when an input layer changes during a streamed snapshot.
- QGIS expression fields, joined fields, dates and UTC timestamps in the snapshot.
- Category field renaming, hidden classification-field rejection and graduated boundary mapping.
- English, Japanese region variants, unsupported-language and untranslated-string fallback.
- HTTP byte ranges, HEAD and path-traversal rejection on the loopback preview server.
- Dialog construction, settings collection, per-layer and bulk PMTiles toggles.

The full dialog smoke test drives QTimer snapshots, asynchronous thumbnail rendering, QgsTask conversion, the isolated validator, result tabs and attribute paging. The two-park sample produced **zero official errors and zero warnings**. Screenshot capture uses an explicit offscreen font, without changing plugin fonts.

The final ZIP was extracted to a separate directory and the same end-to-end GUI build was run using the extracted plugin and its bundled validator. It completed successfully with zero official errors and warnings. The QGIS plugin-manager metadata requirements were checked against the installed QGIS version. The automated suite contains **13 passing tests**.

The browser smoke test uses actual Edge/Chromium, loads the generated PMTiles/style from the local server, waits for the map to load and asserts rendered features and no JavaScript/map errors. Tile features can appear more than once because of tile boundaries, so rendered-feature count is not treated as the analysis dataset's feature count.

## Boundaries of the evidence

### Synthetic scale results

The complete point-grid generation, export, public-value/geometry verification and official validation succeeded at all three sizes. Each output had zero rashid errors and warnings.

| Features | Total elapsed | Included snapshot generation | Catalog size |
|---:|---:|---:|---:|
| 10,000 | 5.59 s | 0.38 s | 145,701 bytes |
| 100,000 | 35.81 s | 6.03 s | 1,348,676 bytes |
| 1,000,000 | 374.11 s | 66.41 s | 13,320,806 bytes |

These are development-machine measurements, with other checks running concurrently. They are not performance guarantees. The million-row test exercised multiple row groups and disk-backed ordering; the earlier single-row-group fixture also passed after the sorting fix. PMTiles and thumbnails were intentionally off in these scale tests and were exercised separately by GUI and browser tests.

### Remaining compatibility checks

- The shipped package has not been published to the QGIS plugin registry or installed into the user's existing QGIS profile.
- macOS, Linux, QGIS 4/Qt6 and other Python ABIs need separate packaging and validation.
- Portolan Browser interoperability has not been exercised against a separately installed Browser release; the generated catalog is checked by rashid and the bundled MapLibre preview.
- GUI visual review covers the Japanese result view; all UI strings use the same English-first translation mechanism.
- Scale tests use synthetic point grids. They do not establish equivalent timing for complex polygons, dense PMTiles or remote data providers.
- File generation success and local validation do not assert hosting compliance or exact visual equivalence for unsupported QGIS styles.

## Later releases

COG/raster scenes, catalog hierarchy from groups, import/merge of arbitrary existing catalogs, upload and live hosting checks, partitioning, incremental rebuild, advanced styling and multilingual STAC trees remain outside the initial release, as specified in the design.
