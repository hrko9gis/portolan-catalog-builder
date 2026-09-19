"""Local export checks only; never a full Portolan conformance verdict."""
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit


def check_catalog(root):
    root = Path(root).resolve()
    findings = []

    def fail(path, message):
        findings.append({'severity': 'error', 'rule_id': 'EXPORT-FILES',
                         'path': str(path.relative_to(root)), 'message': message})

    for name in ('catalog.json', 'README.md', 'AGENTS.md', 'VALIDATION.md'):
        if not (root / name).is_file():
            fail(root / name, 'Required output file missing')
    for path in root.rglob('*.json'):
        try:
            document = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(document, dict):
                raise ValueError('Expected a JSON object')
            if path.name not in ('catalog.json', 'collection.json'):
                continue
            expected = 'Catalog' if path.name == 'catalog.json' else 'Collection'
            for key in ('id', 'description', 'links', 'stac_version'):
                if key not in document:
                    fail(path, 'Required generated field missing: ' + key)
            if document.get('type') != expected:
                fail(path, 'Unexpected catalog object type')
            references = list(document.get('links', [])) + list(document.get('assets', {}).values())
            for reference in references:
                href = reference.get('href', '')
                url = urlsplit(href)
                if url.scheme or url.netloc:
                    continue  # Remote links are explicitly not checked.
                target = (path.parent / unquote(url.path)).resolve()
                if not href or not target.is_relative_to(root) or not target.is_file():
                    fail(path, 'Missing or unsafe local reference: ' + href)
        except (ValueError, OSError, AttributeError, TypeError) as exc:
            fail(path, str(exc))
    return findings
