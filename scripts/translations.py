"""Development-only: create TS and compile using a supplied Qt lrelease."""
import json
from pathlib import Path
import subprocess
import sys
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent

folder = Path(__file__).resolve().parents[1] / 'portolan_catalog_builder/i18n'
translations = json.loads((folder / 'ja.json').read_text(encoding='utf-8'))
root = Element('TS', version='2.1', language='ja_JP', sourcelanguage='en')
context = SubElement(root, 'context')
SubElement(context, 'name').text = 'Portolan'
for source, translation in translations.items():
    message = SubElement(context, 'message')
    SubElement(message, 'source').text = source
    SubElement(message, 'translation').text = translation
indent(root)
ElementTree(root).write(folder / 'ja.ts', encoding='utf-8', xml_declaration=True)
subprocess.run([sys.argv[1], str(folder / 'ja.ts'), '-qm', str(folder / 'ja.qm')], check=True)
