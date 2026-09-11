"""An absolute script entrypoint, run with the configured Python's isolated mode."""

import json
from pathlib import Path
import sys

if sys.version_info < (3, 11):
    print(json.dumps({"schema": 1, "state": "ERROR", "code": "PYTHON_VERSION"}))
    raise SystemExit(20)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from hermes_gateway_herdr.cli import main
except ImportError:
    print(json.dumps({"schema": 1, "state": "ERROR", "code": "DEPENDENCY_MISSING"}))
    raise SystemExit(20)

raise SystemExit(main())
