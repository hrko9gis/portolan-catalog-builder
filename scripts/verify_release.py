"""Record reproducible checks against the exact release ZIP, without installing it."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qgis-python', required=True)
    args = parser.parse_args()
    archive = ROOT / 'dist/portolan_catalog_builder-0.2.0.zip'
    run = ROOT / 'verification' / ('release-0.2.0-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    run.mkdir(parents=True)
    extracted = ROOT / '.test-output' / ('verified-package-' + str(time.time_ns()))
    manifest = {'started_utc': datetime.now(timezone.utc).isoformat(),
                'archive': str(archive), 'bytes': archive.stat().st_size,
                'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                'extracted': str(extracted), 'checks': []}

    def save():
        (run / 'results.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    def check(name, command, timeout=180, env=None):
        print('Checking:', name, flush=True)
        started = time.monotonic()
        try:
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=timeout)
            output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
            code = result.returncode
        except (OSError, subprocess.TimeoutExpired) as exc:
            output, code = str(exc), -1
        (run / f'{name}.log').write_text(output, encoding='utf-8')
        manifest['checks'].append({'name': name, 'command': command, 'exit_code': code,
                                   'status': 'passed' if code == 0 else 'failed',
                                   'seconds': round(time.monotonic() - started, 2), 'log': f'{name}.log'})
        save()
        print(name, 'passed' if code == 0 else 'FAILED', flush=True)
        return code, output

    with zipfile.ZipFile(archive) as zipped:
        for name in zipped.namelist():
            if not (extracted / name).resolve().is_relative_to(extracted.resolve()):
                raise ValueError('Unsafe archive path')
        zipped.extractall(extracted)
        manifest['contains_vendor'] = any('/_vendor/' in n for n in zipped.namelist())
    assert not manifest['contains_vendor']
    assert archive.with_suffix('.zip.sha256').read_text().split()[0] == manifest['sha256']
    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'
    env['PCB_TEST_PACKAGE'] = str(extracted)
    check('publication', [sys.executable, 'scripts/check_publication.py', '--zip', str(archive)], env=env)
    check('unit-integration', [args.qgis_python, 'scripts/run_tests.py'], env=env)
    catalogs = []
    for locale in ('en', 'ja'):
        code, output = check(f'gui-{locale}', [args.qgis_python, 'scripts/gui_smoke.py', str(extracted), locale], env=env)
        if code == 0:
            catalog = re.search(r'GUI build passed: (.+)', output).group(1).strip()
            catalogs.append(catalog)
            shutil.copyfile(ROOT / f'.test-output/gui-result-{locale}.png', run / f'gui-{locale}.png')
            shutil.copyfile(Path(catalog + '.build-report') / 'build-report.json', run / f'build-report-{locale}.json')
    if catalogs:
        check('browser', [sys.executable, 'scripts/browser_smoke.py', str(extracted), catalogs[-1]], env=env)
        if (ROOT / '.test-output/pmtiles-preview.png').is_file() and manifest['checks'][-1]['exit_code'] == 0:
            shutil.copyfile(ROOT / '.test-output/pmtiles-preview.png', run / 'pmtiles-preview.png')
        # Development-only independent verifier; intentionally not in the release ZIP.
        report = run / 'external-validation.json'
        code, _ = check('external-validation', [args.qgis_python, 'portolan_catalog_builder/validation_worker.py',
                                               catalogs[-1], str(report)], env=env)
        if code == 0:
            validation = json.loads(report.read_text(encoding='utf-8'))
            manifest['external_validation'] = {key: validation.get(key) for key in ('passed', 'error_count', 'warning_count')}
            if not validation.get('passed') or any(f.get('rule_id', '').endswith('-000') for f in validation.get('findings', [])):
                manifest['checks'][-1]['status'] = 'failed'
    manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
    manifest['all_passed'] = len(manifest['checks']) == 6 and all(c['status'] == 'passed' for c in manifest['checks'])
    save()
    print('Evidence:', run, flush=True)
    return 0 if manifest['all_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
