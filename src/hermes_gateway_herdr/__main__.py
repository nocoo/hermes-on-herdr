"""An absolute script entrypoint, run with the configured Python's isolated mode."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hermes_gateway_herdr.bootstrap import recover_failed_supervisor

if sys.version_info < (3, 11):
    print(json.dumps({"schema": 1, "state": "ERROR", "code": "PYTHON_VERSION"}))
    raise SystemExit(recover_failed_supervisor(20))

try:
    from hermes_gateway_herdr.cli import main
except ImportError:
    print(json.dumps({"schema": 1, "state": "ERROR", "code": "DEPENDENCY_MISSING"}))
    raise SystemExit(recover_failed_supervisor(20))

raise SystemExit(recover_failed_supervisor(main()))
