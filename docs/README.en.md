<p align="center">
  <img src="../assets/brand/icon-rounded.png" width="128" alt="hermes on herdr logo" />
</p>
<h1 align="center">hermes on herdr</h1>
<p align="center">Run Hermes in Herdr with optional monitoring.</p>
<p align="center"><a href="../README.md">简体中文</a> · <a href="README.md">Documentation</a> · <a href="../examples/README.md">Configuration</a></p>

**hermes on herdr** is a Herdr plugin that runs a dedicated Hermes Gateway inside a real pane. A supervisor manages its lifecycle, and the Gateway inherits the control environment of its owning Herdr session. Run intent, process identity and ownership are recorded; a paused Gateway requires an explicit resume.

![hermes on herdr monitoring two Profiles with offline demo data](evidence/dashboard-two.png)

## The experience

- Start on the managed Gateway's status page. Press **Enter** to open monitoring. “Always open on startup” is off by default; save your choice with Space or a mouse click.
- Monitor multiple Hermes Profiles, including status, CPU, memory and process trends, with the Herdr-managed instance highlighted. Adjust the layout, theme, animation and sampling interval; the default is two seconds.
- Manage the Gateway with `start`, `pause`, `resume`, `stop` and `restart`. Read JSON diagnostics through `status`, `doctor` and `logs`.
- The supervisor uses singleton locks, identity checks, bounded retries and circuit breaking. Unknown launch outcomes and live orphan processes are preserved for diagnosis before replacement.

See the [dashboard guide](14-hqtui监控面板.md) for previews, controls and resource measurements.

## Get started

This is a development release. Use Python 3.11+ from a configured Hermes virtual environment with [psutil and PyYAML](../requirements.txt). The repository includes pinned hqtui source. The inspected host baseline is Herdr v0.9.0 and Hermes Agent v0.21.1; exact versions and commits are recorded in the [source evidence](09-源码证据索引.md).

```sh
git clone https://github.com/nocoo/hermes-on-herdr.git
cd hermes-on-herdr
./bin/hermes-on-herdr --help
```

Help needs no configuration. Before connecting a Gateway, follow the [configuration examples](../examples/README.md) to prepare a separate Herdr session, an existing dedicated Hermes Profile and a private configuration directory. The [implementation and acceptance plan](05-实现步骤.md) covers installation and integration. There is no automatic Profile initializer.

Once configured, replace the placeholder with your actual `config.json`:

```sh
./bin/hermes-on-herdr --config /absolute/config.json status --json
./bin/hermes-on-herdr --config /absolute/config.json doctor --json
./bin/hermes-on-herdr --config /absolute/config.json bind --dry-run
./bin/hermes-on-herdr --config /absolute/config.json dashboard
```

The configuration directory uses mode `0700`; `config.json` and `runtime-python` use `0600`. The interpreter hint contains one absolute path matching `python_bin`.

## Everyday commands

Append these commands to `./bin/hermes-on-herdr --config /absolute/config.json`:

| Command | Behavior |
| --- | --- |
| `bind --dry-run` | Show the binding plan for an existing dedicated Profile; also the default for `bind` |
| `bind --apply` | Create paused control state; an explicit `start` then permits running |
| `start` / `resume` | Save run intent and ensure the Gateway; check READY after the ACK |
| `pause` / `stop` | Persist paused intent, then notify the supervisor |
| `stop --wait 30` | Wait up to 30 seconds and verify shutdown before reporting completion |
| `restart` | Request a restart for an allowed instance, preserving paused intent |
| `status --require-ready` | Succeed only when identity, runtime state and expected platforms satisfy READY |
| `logs --lines 50` | Read structured lifecycle events |
| `dashboard --startup` | Show startup status and offer the full monitor |
| `dashboard --snapshot` / `dashboard --json` | Print one text or JSON monitoring snapshot |
| `dashboard --demo-profiles 2` | Preview a two-Profile dashboard with synthetic data |

For control commands outside a hook, supply the bound owner with the global `--owner-socket /absolute/bound.sock` option. The [command contract](12-离线实现与验证.md#124-当前命令契约) covers all flags, exit codes and retry rules.

## Development and validation

```sh
/absolute/path/to/hermes/venv/bin/python -I -B tests/run.py
```

Tests use temporary directories, fake Herdr RPC, controlled Gateway processes and real PTYs. They do not invoke installed Herdr/Hermes entry points. The latest saved [153-test run](evidence/dashboard-unittest.txt) covers lifecycle races, identity checks, monitoring, startup preferences, terminal input and renderer failures. Reproducible resource measurements are in the [dashboard guide](14-hqtui监控面板.md#146-测试与测量).

Cherry reached READY under plugin supervision, and the user confirmed messaging. A standalone dashboard also completed a live read-only preview. See the [integration record](13-cherry接入与验证.md) for the validation status of embedded activation, cold start, shutdown, explicit pane interaction, Linux and live handoff. READY establishes process and platform readiness; model calls and end-to-end messaging require their own checks.

## Documentation

Detailed guides and research records are in Chinese.

- [Documentation index](README.md): routes for users, developers and research, with current validation scope.
- [Configuration examples](../examples/README.md): interpreter, dedicated Profile, private paths and binding.
- [Dashboard guide](14-hqtui监控面板.md): startup page, layouts, controls, sampling and performance.
- [Security and operations](07-安全与运维.md): permissions, diagnostics, pause and upgrade boundaries.
- [Architecture](02-系统架构.md) and [lifecycle](03-生命周期设计.md): controller, supervisor, locks and recovery.
- [Brand identity](../assets/brand/README.md): logo usage, original source and Hexly presentation.

The brand is **hermes on herdr**. The repository and command are named `hermes-on-herdr`; internal identifiers and historical names are documented in the [naming conventions](README.md#命名约定).
