"""Package source and web assets, excluding the external validator."""
from pathlib import Path
import configparser
import hashlib
import zipfile
root = Path(__file__).resolve().parents[1]
plugin = root / 'portolan_catalog_builder'
metadata = configparser.ConfigParser()
metadata.read(plugin / 'metadata.txt', encoding='utf-8')
version = metadata['general']['version']
required = ['i18n/ja.qm', 'LICENSE', 'help/validation-en.md', 'help/validation-ja.md',
            'preview/vendor/pmtiles.js', 'preview/vendor/PMTILES-LICENSE.txt',
            'preview/vendor/maplibre-gl.js', 'preview/vendor/maplibre-gl.css', 'preview/vendor/MAPLIBRE-LICENSE.txt']
for name in required:
    if not (plugin / name).is_file():
        raise SystemExit(f'Missing release input: {name}')
dist = root / 'dist'
dist.mkdir(exist_ok=True)
target = dist / f'portolan_catalog_builder-{version}.zip'
with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for filename in ('README.md', 'CHANGELOG.md', 'BUILDING.md', 'CONTRIBUTING.md', 'THIRD_PARTY_NOTICES.md'):
        text = (root / filename).read_text(encoding='utf-8').replace('portolan_catalog_builder/help/', 'help/')
        archive.writestr('portolan_catalog_builder/' + filename, text)
    for folder in ('docs', 'examples'):
        for path in sorted((root / folder).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                archive.write(path, 'portolan_catalog_builder/' + path.relative_to(root).as_posix())
    for path in sorted(plugin.rglob('*')):
        relative = path.relative_to(plugin)
        if '_vendor' in relative.parts or '__pycache__' in relative.parts:
            continue
        if not path.is_file() or path.suffix in ('.pyc', '.pyo') or path.name == 'validation_worker.py':
            continue
        if path.suffix.lower() in {'.dll', '.pyd', '.so', '.dylib', '.exe', '.a', '.lib'}:
            raise SystemExit(f'Native binary must not be packaged: {relative}')
        archive.write(path, 'portolan_catalog_builder/' + relative.as_posix())
if target.stat().st_size > 25_000_000:
    raise SystemExit('Package exceeds 25 MB.')
digest = hashlib.sha256(target.read_bytes()).hexdigest()
target.with_suffix('.zip.sha256').write_text(digest + '  ' + target.name + '\n', encoding='ascii')
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    assert not any('/_vendor/' in name for name in archive.namelist())
print(f'{target}\n{target.stat().st_size:,} bytes\nSHA256 {digest}')
