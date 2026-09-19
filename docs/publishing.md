# QGIS repository publication status

[日本語](publishing-ja.md)

Reviewed against the official guidance on 2026-09-16:

- https://plugins.qgis.org/docs/publish
- https://plugins.qgis.org/docs/approval
- https://docs.qgis.org/3.44/en/docs/pyqgis_developer_cookbook/plugins/plugins.html

## Source repository

Publish the readable source at the author's **public** GitHub repository
[hrko9gis/portolan-catalog-builder](https://github.com/hrko9gis/portolan-catalog-builder).
Enable Issues. A separate website is not required:
the root README describes installation, use, supported environments and limits.

The following fields are configured in `portolan_catalog_builder/metadata.txt`:

| Field | Value |
| --- | --- |
| `homepage` | `https://github.com/hrko9gis/portolan-catalog-builder#readme` |
| `repository` | `https://github.com/hrko9gis/portolan-catalog-builder` |
| `tracker` | `https://github.com/hrko9gis/portolan-catalog-builder/issues` |
| `author` | Kohei Hara |
| `email` | hrko9gis@gmail.com |

The repository URL and author name were supplied by the author. The email is
the existing public contact in
[GSI-AddressSearch metadata](https://github.com/hrko9gis/GSI-AddressSearch/blob/main/metadata.txt).
Public access to the new repository and Issues must still be verified after upload.
The source repository must
contain the code corresponding to the submitted version, not just a ZIP.

The repository includes English user documentation, Japanese instructions,
design and validation notes, GPL license text, third-party notices, changelog,
synthetic sample data, tests and build instructions. Commit these files and the
plugin source; preserve the existing dependency and generated-output exclusions.

## Version 0.2.0 distribution

Native validator dependencies are excluded. Basic export checks remain local;
detailed validation is performed by the user in a separate environment using the
included guide. This addresses the old 84 MB bundle and native-binary inclusion.
The plugin still requires GDAL Parquet support and PyArrow in QGIS; PMTiles support
is needed only when requested. Linux, macOS and QGIS 4 remain untested.
Official approval and public repository visibility must still be verified.

## Pre-submission checks

Run the local checker from the source root:

```text
python scripts/check_publication.py
python scripts/check_publication.py --zip dist/portolan_catalog_builder-0.2.0.zip
```

It checks required metadata, documentation, source layout and, when supplied,
the archive's metadata, size, native binaries and required files. It intentionally
fails for missing author URLs/contact, bundled native binaries or oversized archives.
It does not replace the official security scan or manual review, and does not
verify public access to URLs.

Before uploading, check the public links while signed out of GitHub, enable
Issues, replace any missing metadata, run tests on each declared platform and
verify that the submitted ZIP matches the published source version. Include
upstream license texts for all redistributed dependencies. Final approval is
made by the QGIS repository maintainers.
