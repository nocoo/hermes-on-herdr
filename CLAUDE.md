# hermes on herdr

Herdr plugin that binds a trusted Hermes profile Gateway into the current session.
Profile: cli-library
Direction: [docs/02-系统架构.md](docs/02-系统架构.md). Frameworks must not rewrite this file.

## Sources of Truth

This file is the **contract**. Hooks, CI, and config are **enforcement**. If they disagree, that is a failure — raise enforcement to match this file; never lower the contract to a weaker hook.

| Fact | Where |
|---|---|
| Agent handbook | this file |
| Human docs | README.md, `docs/NN-*.md` |
| Version | `herdr-plugin.toml` / package `__version__` `0.1.2`, display `v0.1.2` |
| Enforcement | `.github/workflows/tests.yml`, `tests/run.py` |
| Machine rules | global `AGENTS.md`, `rules/git-commit.md` |
| Accidents | [Retrospective.md](Retrospective.md) |
| Env files | never commit Hermes/channel tokens; fake secrets use sentinel strings only |

## Project Invariants

- Binding is an explicit trusted Profile + owner socket. Install does not authorize arbitrary Hermes or other profiles.
- Session control is Herdr API for that session, not an OS sandbox. Same-UID Hermes still has host privileges.
- Do not run tests against the default Profile or a live user Gateway. Offline suite must not import Hermes main or call installed Herdr/Hermes binaries.
- Optional HTTP dashboard binds `127.0.0.1` only, read-only, no Gateway control.
- Herdr Unix socket stays local. Channel credentials are operator-configured, not invented by the plugin.
- Startup must not `pip install`; reuse the configured Hermes venv (`requirements.txt` is for the plugin extras).

## Stack / Layout

| Component | Choice |
|---|---|
| Language | Python 3.11 / 3.14 |
| Package manager | pip into a dedicated venv (`python -m venv --copies`) |
| Runtime | Herdr plugin + `./bin/hermes-on-herdr` |
| Lint | none in CI |
| Tests | `unittest` via `tests/run.py`; optional `tools/test_coverage.py` |
| Data | plugin state under isolated XDG dirs in tests (`/tmp/hgh-*`) |

```
src/hermes_gateway_herdr
tests/test_*.py  tests/run.py
bin/  docs/  examples/
```

## Commands

```bash
python -m venv --copies .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -I -B tests/run.py          # isolated local suite only
# optional coverage (must be that venv, not system python):
.venv/bin/python tools/test_coverage.py
./bin/hermes-on-herdr --help
```

Do not run recover/start/supervise against a production session from this handbook.

## Verification

Status: `enforced` | `planned` | `manual` | `N/A`.
6DQ = L1/L2/L3 + G1/G2 + D1. Native coverage may expose fewer metrics — remaining gap stays planned. Required bar remains ≥ 95% where measurable.

| Change | Proof | Status | Evidence |
|---|---|---|---|
| Logic | L1 unittest of locks/identity/lifecycle | enforced | CI `tests.yml` matrix OS×Python 3.11/3.14 → `tests/run.py`. No 95% threshold in `tools/test_coverage.py` → coverage bar still **planned** |
| API / schema | L2 fake Herdr RPC / fake Gateway | enforced | same offline suite (`tests/test_rpc.py`, process fixtures). Not real Herdr HTTP |
| UI path | L3 isolated real Herdr session + Profile | planned | docs/06 requires live E2E with `HGH_TEST_*`; CI does not run it |
| Types / lint | G1 0 error, 0 warning | planned | no ruff/mypy/gate in CI |
| Deps / secrets | G2 osv-scanner + gitleaks | planned | `tests.yml` has no security job. Plugin is executable — G2 still required, not N/A |
| Test isolation | D1 `/tmp/hgh-*`, fake RPC, no live Gateway | enforced | `tests/run.py` docstring; `tests/process_fixture.py`; fail closed on prod paths |
| Bundler output | n/a | N/A | no JS bundler |
| Docs | numbered docs if behavior changed | manual | human review |
| Release | tag matches `__version__` | enforced | tests.yml tag check; `release.yml` |

CLI process E2E against a disposable Herdr session is L3, not N/A.

## Resources / Isolation

| Purpose | Port / resource | Isolation |
|---|---|---|
| Offline tests | `/tmp/hgh-*` | auto create/destroy; fake binaries only |
| Dashboard | `127.0.0.1` only | read-only |
| Live E2E | separate XDG + Profile + bot | `HGH_TEST_*` required; never default Profile |

Never `pkill hermes` or kill PIDs not captured by the test.

## Operations / Release

- Entry: documented in [docs/15-发布与安装.md](docs/15-发布与安装.md)
- Auth: repo owner; plugin install on the operator machine
- Before ship: offline suite green on both OS/Python; tag must equal `v` + `__version__`
- Runbook: [docs/16-首次安装与Profile关联.md](docs/16-首次安装与Profile关联.md)

## Retrospective

| Kind | Where |
|---|---|
| Accident narrative | [Retrospective.md](Retrospective.md) |
| Project-specific rule that will recur | one line here (cap ~10) |
| Cross-project lesson | nmem / global `AGENTS.md` / `rules/` |
| Deterministically checkable rule | hook or test, not prose |

- Offline PASS does not certify live Herdr/Hermes/channel E2E.
- Cleanup may kill only PIDs the test started; never `killall` by name.
