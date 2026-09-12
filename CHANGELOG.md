# Changelog

## 0.1.0 — 2026-09-12

Install with `herdr plugin install nocoo/hermes-on-herdr --ref v0.1.0`. The [GitHub Release](https://github.com/nocoo/hermes-on-herdr/releases/tag/v0.1.0) records the release commit and CI; the [installation guide](docs/15-发布与安装.md) covers configuration, compatibility, upgrades and handoff.

- Run an existing dedicated Hermes Profile's Gateway inside its owning Herdr pane, with persistent Start/Pause/Resume/Stop/Restart intent, process identity checks, bounded recovery and circuit breaking.
- Show a lightweight Gateway startup page. Open the full hqtui monitor on demand; automatic opening is off by default and can be saved as a preference.
- Monitor multiple local Profiles with the managed instance highlighted, responsive layouts and the Hermes caduceus. Sampling remains bounded as the number of Profiles grows.
- Show `v0.1.0` in both TUI views and provide configuration-free `--version`. Keep the legacy launcher and plugin ID compatible with existing installations.
- Keep launcher help available before setup, including inside a newly installed plugin's environment.
- Offer an optional read-only loopback panel with `dashboard --http-port 8767`. `/health` returns 200 only for fresh READY telemetry with verified ownership and connected expected platforms; closing the panel leaves the Gateway running.
- Support Linux kernels without `pidfd_open` through an identity-checked fallback. Run isolated tests on Ubuntu and macOS with Python 3.11 and 3.14 in CI.
- Handle macOS removing argv before publishing zombie status during process teardown. Briefly wait for proof of exit without reaping the child or losing its restart/fuse exit code; unreadable live processes remain errors.

Compatibility currently requires Herdr 0.9.0 and Hermes commit `b7ac3ba1cdf89f94dfe86de27e01358b194f4053`. Hermes Profile configuration remains the user's responsibility. The [first-run association wizard](docs/16-首次安装与Profile关联.md) is planned; manual configuration and binding are available now.

Local macOS validation: 166 isolated tests pass on Python 3.11 and 3.14, plus 400 real process teardown checks. CI covers Ubuntu 24.04 and macOS on both Python versions. Historical Cherry messaging was confirmed by the user; current installation and handoff evidence belongs in the [integration record](docs/13-cherry接入与验证.md). Linux host integration, complete Herdr cold-start/shutdown and live Herdr update handoff remain separate validation work. CI uses controlled fake Gateways and does not establish those live guarantees.

The repository has no project-wide license grant. Vendored hqtui retains its own MIT license; publishing a source release does not extend that license to this project's code.
