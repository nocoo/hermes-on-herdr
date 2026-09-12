"""Optional coverage.py runner for the isolated suite, including sanitized subprocesses."""

from pathlib import Path
import site
import subprocess
import sys
import tempfile

import coverage


def main():
    if sys.prefix == sys.base_prefix:
        raise SystemExit("Run in a dedicated virtualenv created with python -m venv --copies.")
    root = Path(__file__).resolve().parents[1]
    cache = root / ".cache"
    cache.mkdir(exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="coverage-", dir=cache))
    config = output / "coverage.ini"
    config.write_text(
        f"[run]\nbranch = True\nsource = {root / 'src/hermes_gateway_herdr'}\n"
        f"data_file = {output / '.coverage'}\nparallel = True\npatch = _exit, execv\n"
        "\n[report]\nshow_missing = True\n"
    )
    # Fixture envs and production child_env deliberately strip coverage variables.
    # Instrument only this disposable venv, without weakening that allowlist.
    pth = Path(site.getsitepackages()[0]) / "hermes_test_coverage.pth"
    with pth.open("x") as stream:
        stream.write(f"import os; os.environ['COVERAGE_PROCESS_START'] = {str(config)!r}; "
                     "import coverage; coverage.process_startup()\n")
    try:
        with (output / "tests.log").open("w") as log:
            result = subprocess.run([sys.executable, "-I", "-B", str(root / "tests/run.py")],
                                    cwd=root, stdout=log, stderr=subprocess.STDOUT)
    finally:
        pth.unlink()
    measured = coverage.Coverage(config_file=str(config))
    measured.combine()
    measured.save()
    measured.report()
    measured.json_report(outfile=str(output / "coverage.json"))
    print(f"Tests exited {result.returncode}; logs and coverage: {output}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
