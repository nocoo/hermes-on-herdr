# Changelog

## 0.1.3 — 2026-09-18

Install with `herdr plugin install nocoo/hermes-on-herdr --ref v0.1.3`. Existing installations must follow the [upgrade sequence](docs/15-发布与安装.md#升级与回滚) so the supervisor loads the new code.

- Replace the exact Herdr 0.9.0 check with live protocol 22 validation and the stable `>=0.9.0,<0.10.0` compatibility range. Herdr 0.9.1 and later compatible patches no longer fail solely because their release number changed.
- Reject unknown protocols, missing or malformed handshake fields, prereleases and releases outside the reviewed API family before creating resources. Recheck the live server during supervision; an incompatible protocol change stops the owned Gateway safely.
- Apply the same check to the dependency-free recovery popup. Doctor reports the accepted server version/protocol, supported range and useful rejection messages.
- Add eight regression tests; the complete offline suite contains 214 tests. Verify real 0.9.1 plugin registration, workspace/pane creation, ownership and supporting RPCs in an isolated native session. See the [compatibility policy and evidence](docs/18-Herdr兼容策略.md).

No runtime dependencies, persistent schemas, plugin IDs or Hermes source requirements changed. Native Linux, real Gateway handoff and message/model round trips are not established by this release's isolated checks.

## 0.1.2 — 2026-09-14

Install with `herdr plugin install nocoo/hermes-on-herdr --ref v0.1.2`. Follow the [upgrade sequence](docs/15-发布与安装.md#升级与回滚) for an existing installation: Stop now keeps the dashboard and supervisor alive, so disable the plugin and close its verified owned pane before replacing the checkout.

- Open the full dashboard immediately in the dedicated Herdr tab. Keep it available while the Gateway is paused, blocked or fused; remove the initial dashboard question and ignore the old `auto_open` preference.
- Restore through Herdr startup, workspace focus and pane lifecycle hooks. Preserve running/paused intent, singleton ownership and circuit breaking; `monitor` restores and focuses the dashboard without resuming a paused Gateway.
- Start or retry the Gateway with the dashboard button or Enter. Retry blocked startup checks every 30 seconds and recover a failed dashboard renderer after about five seconds. A late startup check cannot override a newer Pause.
- Add an independent recovery screen through the bare `hermes-on-herdr` command and the native **Recovery & Repair** action. System Python can display diagnosis when the configured runtime is unavailable, with explicit actions to restore the dashboard, repair the runtime or dependencies, and launch or attach the saved Herdr session.
- Persist recovery instructions in the dedicated tab and pane labels. Explicit recovery can release creation tickets from proven-dead controllers; live orphans, unknown launches and ambiguous ownership still require diagnosis.
- Leave Hermes's own plugin selection to Hermes. Stop inspecting its plugin configuration or forcing project plugins off. Reduce repeated process checks while retaining identity verification.
- Bring the offline suite to 206 tests on both supported Python versions. An isolated native Herdr 0.9.0 check verifies fallback UI, the recovery popup and labels surviving server cold restart; see [recovery validation](docs/evidence/recovery-validation.txt).

Plugin IDs, persistent schema and runtime dependencies remain unchanged. Other dashboard preferences are preserved. Compatibility remains Herdr 0.9.0 and Hermes v0.21.1 at `b7ac3ba1cdf89f94dfe86de27e01358b194f4053`. No OS autostart service or independent periodic ensure daemon is installed. Full live host restart, Linux integration, online Herdr upgrade handoff and fresh message/model round trips remain unverified. The earlier intermittent FIFO CLI test timeout did not recur in the two recorded local runs; its cause remains unidentified.

## 0.1.1 — 2026-09-12

Install with `herdr plugin install nocoo/hermes-on-herdr --ref v0.1.1`. Existing installations must follow the [stop, verify, install and resume sequence](docs/15-发布与安装.md#升级与回滚); replacing the checkout does not update a running supervisor.

- Reject malformed local control requests without terminating the supervisor or its Gateway. Malformed replies no longer hide an already committed Pause.
- Require explicit absolute plugin and terminal paths. Reject control-variable overrides hidden behind quoted `.env` keys, a UTF-8 BOM or CR line endings.
- Refuse FIFO event logs and Gateway locks without blocking. Validate damaged intent/pending state and deeply nested YAML with bounded, sanitized errors.
- Add 19 regression tests, bringing the suite to 186. The [quality assessment](docs/17-插件质量评估.md) records 88.54% statement and 81.32% branch coverage, including isolated CLI and supervisor processes.
- Clarify trusted Profile selection, the bound session's control context, existing Hermes channels and the local security boundary in both READMEs.

The plugin ID, pane ID, persistent schema and runtime dependencies are unchanged. Compatibility remains pinned to Herdr 0.9.0 and Hermes v0.21.1 at `b7ac3ba1cdf89f94dfe86de27e01358b194f4053`. Automatic orphan recovery and the first-run association wizard remain unimplemented; offline tests do not establish live host or messaging guarantees. See the [release guide](docs/15-发布与安装.md) for current validation and limitations.

## 0.1.0 — 2026-09-12

Install with `herdr plugin install nocoo/hermes-on-herdr --ref v0.1.0`. The [GitHub Release](https://github.com/nocoo/hermes-on-herdr/releases/tag/v0.1.0) records the release commit and CI; the [installation guide](docs/15-发布与安装.md) covers configuration, compatibility, upgrades and handoff.

- Run an existing dedicated Hermes Profile's Gateway inside its owning Herdr pane, with persistent Start/Pause/Resume/Stop/Restart intent, process identity checks, bounded recovery and circuit breaking.
- Show a lightweight Gateway startup page. Open the full hqtui monitor on demand; automatic opening is off by default and can be saved as a preference.
- Monitor multiple local Profiles with the managed instance highlighted, responsive layouts and the Hermes caduceus. Sampling remains bounded as the number of Profiles grows.
- Show `v0.1.0` in both TUI views and provide configuration-free `--version`. Keep the legacy launcher and plugin ID compatible with existing installations.
- Keep launcher help available before setup, including inside a newly installed plugin's environment.
- Offer an optional read-only loopback panel with `dashboard --http-port 8767`. `/health` returns 200 only for fresh READY telemetry with verified ownership and connected expected platforms; closing the panel leaves the Gateway running.
- Support Linux kernels without `pidfd_open` through an identity-checked fallback. Run isolated tests on Ubuntu and macOS with Python 3.11 and 3.14 in CI.
- Bind the numeric loopback HTTP address without reverse DNS, so local panel startup does not depend on hostname resolution.
- Handle macOS removing argv before publishing zombie status during process teardown. Briefly wait for proof of exit without reaping the child or losing its restart/fuse exit code; unreadable live processes remain errors.

Compatibility currently requires Herdr 0.9.0 and Hermes commit `b7ac3ba1cdf89f94dfe86de27e01358b194f4053`. Hermes Profile configuration remains the user's responsibility. The [first-run association wizard](docs/16-首次安装与Profile关联.md) is planned; manual configuration and binding are available now.

Local macOS validation: 167 isolated tests pass on Python 3.11 and 3.14, plus 400 real process teardown checks. CI covers Ubuntu 24.04 and macOS on both Python versions. Historical Cherry messaging was confirmed by the user; current installation and handoff evidence belongs in the [integration record](docs/13-cherry接入与验证.md). Linux host integration, complete Herdr cold-start/shutdown and live Herdr update handoff remain separate validation work. CI uses controlled fake Gateways and does not establish those live guarantees.

The repository has no project-wide license grant. Vendored hqtui retains its own MIT license; publishing a source release does not extend that license to this project's code.
