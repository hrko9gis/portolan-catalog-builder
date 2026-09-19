# Implementation and verification status ? 0.2.0

Current behavior: local creation of GeoParquet and optional PMTiles, basic data
integrity checks, and explicit external detailed validation. No native validator
is bundled or downloaded. English/Japanese offline guides are included.

See [Japanese verification and remaining work](verification-ja.md). Reproducible
commands, exit codes, exact ZIP SHA-256, reports and screenshots are kept in the
source repository's `verification/` directory. The runner is
`scripts/verify_release.py`; its tests import the extracted ZIP, not the checkout.

The current checks cover automated integration tests, English/Japanese GUI
creation and validation guides, actual browser PMTiles rendering, and independent
rashid checks using the existing development environment. These are separate
from QGIS repository security scanning and manual approval.

The tested environment is Windows x64 / QGIS 3.44.13 / Python 3.12 / GDAL 3.13.2.
Linux, macOS and QGIS 4 are unverified. End-user fresh installation of external
validation tools, independent Portolan Browser interoperability, hosting/CORS,
and production-scale polygon datasets remain separate checks.

The GitHub repository is public with Issues enabled, but the README endpoint
returned HTTP 404 on 2026-09-17 (JST). Publish readable source and documentation
before submitting to the QGIS repository. No upload or submission was performed.

The old 84 MB package and bundled-validation results belong to
[the archived 0.1.0 record](implementation-history-0.1.0.md), not this release.
