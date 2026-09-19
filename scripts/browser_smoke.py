"""Verify actual PMTiles rendering with a local Chromium and no network assets."""
from pathlib import Path
import sys
import json
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if len(sys.argv) > 1:
    sys.path.insert(0, sys.argv[1])
from portolan_catalog_builder.preview import PreviewServer
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
catalog = Path(sys.argv[2]) if len(sys.argv) > 2 else max((p for p in (root / '.test-output').glob('gui-*') if (p / 'catalog.json').is_file()), key=lambda p: p.stat().st_mtime)
import portolan_catalog_builder
print('Testing package:', portolan_catalog_builder.__file__, flush=True)
if len(sys.argv) > 1:
    assert Path(portolan_catalog_builder.__file__).resolve().is_relative_to(Path(sys.argv[1]).resolve())
server = PreviewServer(catalog)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True, args=['--enable-unsafe-swiftshader'])
        page = browser.new_page(viewport={'width': 1000, 'height': 700})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(server.url('parks', 'ja'))
        try:
            page.wait_for_function('window.portolanMap && window.portolanMap.loaded()', timeout=30000)
        except Exception:
            print('Preview error:', page.locator('#error').inner_text(), errors, flush=True)
            raise
        features = page.evaluate('window.portolanMap.queryRenderedFeatures().length')
        assert features > 0, 'No rendered PMTiles features'
        assert not errors, errors
        assert page.locator('#error').inner_text() == '', page.locator('#error').inner_text()
        page.screenshot(path=str(root / '.test-output/pmtiles-preview.png'))
        print(json.dumps({'rendered_features': features, 'errors': errors, 'catalog': str(catalog)}))
        browser.close()
finally:
    server.close()
