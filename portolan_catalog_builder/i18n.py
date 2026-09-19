from pathlib import Path
from qgis.PyQt.QtCore import QCoreApplication, QTranslator
from qgis.core import QgsApplication

def tr(text):
    return QCoreApplication.translate('Portolan', text)

def message(text):
    """Translate known messages while preserving original diagnostic details."""
    lines = []
    for line in str(text).splitlines():
        translated = tr(line)
        if translated == line and ': ' in line:
            prefix, detail = line.split(': ', 1)
            translated = tr(prefix) + ': ' + tr(detail)
        lines.append(translated)
    return '\n'.join(lines)

def language():
    app = QgsApplication.instance()
    code = app.translation() if app else ''
    return 'ja' if str(code).lower().replace('-', '_').split('_')[0] == 'ja' else 'en'

def install():
    translator = QTranslator()
    if language() == 'ja' and translator.load(str(Path(__file__).parent / 'i18n/ja.qm')):
        QCoreApplication.installTranslator(translator)
    return translator
