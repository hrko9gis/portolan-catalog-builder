"""Isolated library worker; never imports QGIS or invokes a CLI tool."""
import json
from pathlib import Path
import sys

runtime = Path(__file__).parent / '_vendor'
if runtime.is_dir():
    sys.path.insert(0, str(runtime))

def main():
    from rashid import validate
    from rashid.data.reader import LocalOnlyReader
    result = validate(sys.argv[1], structural=True, schema=True, data=True,
                      schema_allow_network=False, data_reader_factory=LocalOnlyReader)
    Path(sys.argv[2]).write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()

