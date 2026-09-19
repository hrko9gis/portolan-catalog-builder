"""Check local QGIS publication prerequisites; not an official approval tool."""
import argparse
import configparser
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'portolan_catalog_builder'
NATIVE_SUFFIXES = {'.dll', '.pyd', '.so', '.dylib', '.exe', '.a', '.lib'}


def metadata_errors(text):
    config = configparser.ConfigParser(interpolation=None)
    try:
        config.read_string(text)
    except configparser.Error as error:
        return [f'Invalid metadata: {error}']
    if not config.has_section('general'):
        return ['Missing [general] metadata section.']
    metadata = config['general']
    errors = []
    for key in ('name', 'description', 'about', 'version', 'qgisMinimumVersion',
                'author', 'email', 'homepage', 'repository', 'tracker', 'icon'):
        if not metadata.get(key, '').strip():
            errors.append(f'Missing metadata field: {key}')
    email = metadata.get('email', '')
    if email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        errors.append('Invalid author email.')
    for key in ('homepage', 'repository', 'tracker'):
        value = metadata.get(key, '')
        if not value:
            continue
        parsed = urlsplit(value)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
                or parsed.password or 'OWNER' in value or 'example.' in parsed.hostname):
            errors.append(f'Invalid or placeholder URL: {key}')
    if metadata.get('author') == 'Portolan Catalog Builder contributors':
        errors.append('Confirm and set the public author display name.')
    return errors


def archive_errors(path):
    errors = []
    if path.stat().st_size > 25_000_000:
        errors.append('Archive exceeds the published 25 MB limit.')
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        for filename in ('metadata.txt', '__init__.py', 'LICENSE'):
            if f'{PACKAGE}/{filename}' not in names:
                errors.append(f'Archive missing: {filename}')
        metadata_path = f'{PACKAGE}/metadata.txt'
        if metadata_path in names:
            errors.extend(metadata_errors(archive.read(metadata_path).decode('utf-8-sig')))
            source = (ROOT / PACKAGE / 'metadata.txt').read_bytes()
            if archive.read(metadata_path) != source:
                errors.append('Archive metadata differs from current source; rebuild the archive.')
        binaries = []
        for name in names:
            parts = PurePosixPath(name).parts
            if not parts or parts[0] != PACKAGE or '..' in parts or '\\' in name:
                errors.append(f'Invalid archive path: {name}')
            if '__pycache__' in parts or PurePosixPath(name).suffix in {'.pyc', '.pyo'}:
                errors.append(f'Python cache included: {name}')
            if PurePosixPath(name).suffix.lower() in NATIVE_SUFFIXES or '.so.' in name:
                binaries.append(name)
        if binaries:
            errors.append(f'Archive contains {len(binaries)} native binary files (for example {sorted(binaries)[0]}).')
        if archive.testzip():
            errors.append('Archive CRC check failed.')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', type=Path, help='Also inspect an installation ZIP.')
    args = parser.parse_args()
    errors = []
    for filename in ('README.md', 'LICENSE', 'CHANGELOG.md', 'BUILDING.md',
                     'THIRD_PARTY_NOTICES.md', 'examples/sample-points.geojson',
                     f'{PACKAGE}/__init__.py', f'{PACKAGE}/LICENSE'):
        if not (ROOT / filename).is_file():
            errors.append(f'Missing file: {filename}')
    metadata = ROOT / PACKAGE / 'metadata.txt'
    if metadata.is_file():
        errors.extend(metadata_errors(metadata.read_text(encoding='utf-8-sig')))
    else:
        errors.append('Missing metadata.txt.')
    if args.zip:
        try:
            errors.extend(archive_errors(args.zip))
        except (OSError, zipfile.BadZipFile, UnicodeError) as error:
            errors.append(f'Cannot inspect archive: {error}')
    for error in errors:
        print(f'FAIL: {error}')
    if errors:
        print(f'{len(errors)} publication prerequisite(s) unresolved.')
        return 1
    print('Local file checks passed. Verify public URLs, dependency strategy, platform testing and official review separately.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
