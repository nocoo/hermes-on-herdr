# Vendored dependencies

`hqtui/` contains the unmodified native Python library from
[profullstack/hqtui](https://github.com/profullstack/hqtui/tree/d9a841494bab910403737a8c791d6d96ef52e878/ports/python),
version 0.2.0, commit `d9a841494bab910403737a8c791d6d96ef52e878`, under the MIT license.
Its Python port is not published on PyPI at this baseline. Bundling its 34 library
files makes the dashboard available offline without installing into the Hermes
venv or fetching dependencies at startup. The upstream demo and telemetry
collectors are not included.

[ORIGIN.json](hqtui/ORIGIN.json) records each source file's SHA-256.
[LICENSE](hqtui/LICENSE) and [upstream README](hqtui/README.upstream.md) retain
attribution. Update the complete library and hashes together against an explicit
commit, then run the dashboard rendering, terminal and performance checks.
