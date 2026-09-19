"""Developer-only download of pinned, hash-verified preview assets."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'portolan_catalog_builder'
URLS = {
    'maplibre-gl.js': 'https://unpkg.com/maplibre-gl@5.6.2/dist/maplibre-gl.js',
    'maplibre-gl.css': 'https://unpkg.com/maplibre-gl@5.6.2/dist/maplibre-gl.css',
    'MAPLIBRE-LICENSE.txt': 'https://unpkg.com/maplibre-gl@5.6.2/LICENSE.txt',
    'pmtiles.js': 'https://unpkg.com/pmtiles@4.3.0/dist/pmtiles.js',
    'PMTILES-LICENSE.txt': 'https://raw.githubusercontent.com/protomaps/PMTiles/5897a82a16b233abac7b8f339c019b931c2bbf54/LICENSE',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify local files without network access.')
    args = parser.parse_args()
    expected = json.loads((PLUGIN / 'profiles/runtime-lock.json').read_text(encoding='utf-8'))['web']
    destination = PLUGIN / 'preview/vendor'
    if set(expected) != set(URLS):
        raise SystemExit('Web lock and download manifest do not match.')
    verified = {}
    for name, url in URLS.items():
        path = destination / name
        if path.exists():
            data = path.read_bytes()
        elif args.check:
            raise SystemExit(f'Missing asset: {name}')
        else:
            with urlopen(url, timeout=60) as response:
                data = response.read()
        if hashlib.sha256(data).hexdigest() != expected[name]:
            raise SystemExit(f'SHA-256 mismatch: {name}; existing files were not changed.')
        verified[name] = data
    if not args.check:
        destination.mkdir(parents=True, exist_ok=True)
        for name, data in verified.items():
            (destination / name).write_bytes(data)
    print(f'Verified {len(verified)} preview assets.')


if __name__ == '__main__':
    main()
