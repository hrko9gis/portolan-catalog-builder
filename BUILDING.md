# Build version 0.2.0

Use a QGIS environment with GDAL Parquet support, PyArrow and optional PMTiles
support. Tested on Windows x64, QGIS 3.44.13 / Python 3.12 / GDAL 3.13.2.

From the repository root:

```text
python scripts/fetch_web_assets.py
python scripts/translations.py <path-to-lrelease>
python-qgis-ltr.bat scripts/run_tests.py
python scripts/package.py
python scripts/unpack_release.py
```

The Japanese TS/QM files are committed; translation compilation is needed only
when translations change. Web assets are version-pinned and SHA-256 checked.
No `_vendor` installation is required. Even if it exists in a developer checkout,
the package script excludes it and the legacy `validation_worker.py` helper.
It rejects native binaries and packages above 25 MB.

The ZIP is `dist/portolan_catalog_builder-0.2.0.zip`, with a SHA-256 sidecar.
Run `scripts/gui_smoke.py <extracted-folder>` with QGIS Python to test the actual
package. This must work with no `_vendor` in that extracted folder.
Run `scripts/check_publication.py --zip dist/portolan_catalog_builder-0.2.0.zip`.

For independent detailed validation use the
[external guide](portolan_catalog_builder/help/validation-en.md). The historical
`requirements-runtime.lock` describes the old development validator environment,
not a dependency of the plugin. Never install it over QGIS packages.

Keep dependencies, generated catalogs and ZIPs out of Git. QGIS approval and
cross-platform compatibility require review beyond these local checks.
