# Minimal sample

`sample-points.geojson` contains two synthetic WGS84 points, not observations of
actual facilities. It is provided under the repository's GPL-3.0-or-later license.

1. Add the GeoJSON to QGIS using **Layer > Add Layer > Add Vector Layer**.
2. Open **Portolan Catalog Builder > Create Portolan Catalog**.
3. Select the layer and assign collection ID `sample-points`.
4. Enter catalog metadata and descriptions for `name`, `category` and `value`.
5. Build into a new output folder, once with PMTiles enabled and once disabled.
6. Check validation results and output attributes. GeoParquet should contain two
   records in both runs; PMTiles and its map style should exist only when enabled.

Requires the supported QGIS environment described in the root README. Detailed
validation is external; follow VALIDATION.md in the generated catalog.
