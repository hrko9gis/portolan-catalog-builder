from pathlib import Path
import time
import zipfile

root = Path(__file__).resolve().parents[1]
path = root / 'dist/portolan_catalog_builder-0.2.0.zip'
destination = root / '.test-output' / ('package-' + str(time.time_ns()))
with zipfile.ZipFile(path) as archive:
    for name in archive.namelist():
        target = (destination / name).resolve()
        if not target.is_relative_to(destination.resolve()):
            raise ValueError('Invalid archive path')
    archive.extractall(destination)
(root / '.test-output/package-path.txt').write_text(str(destination), encoding='utf-8')
print(destination)
