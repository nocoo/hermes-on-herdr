# 18 · Herdr compatibility

Version 0.1.3 replaces the exact `ping.version == "0.9.0"` gate. The checked starting point was main `9abd7019421bc1880bbdfba5d1198792a5acb422`; the installed Herdr binary reported 0.9.1. Its live JSON API reports `type: "pong"`, `version: "0.9.1"`, and `protocol: 22`.

## Acceptance contract

The running owner server must return a well-formed pong with an integer protocol in `{22}` and a stable semantic version in `>=0.9.0,<0.10.0`. Build metadata is allowed. Patch versions are compared numerically, without an allowlist of individual releases. Previews and release candidates are rejected. The installed CLI's version or bundled schema cannot substitute for the live server response after an upgrade.

The lower bound limits acceptance to the researched plugin API family. Protocol 22 also exists in older Herdr releases, so protocol alone is insufficient. The exclusive 0.10.0 upper bound is deliberate: Herdr is pre-1.0, and its protocol number describes the wire format rather than a separately versioned plugin API. A new minor release needs a source/API review before expanding this range. Future protocol numbers must also be reviewed, even if the release still says 0.9.x. The manifest retains `min_herdr_version = "0.9.0"`; runtime enforcement supplies the additional checks.

Herdr 0.9.1's advertised capabilities (`live_handoff`, `detached_server_daemon`, `endpoint_protocol_generation`, `surface_interest`, `health_check`) concern server/client features. They do not advertise the plugin methods this project consumes. `herdr api schema --json` is bundled CLI metadata, not live method negotiation. The plugin therefore does not invent capability flags, require unrelated features, or probe mutating methods to discover support. Optional capabilities and extra pong fields are ignored. If upstream adds a versioned plugin capability contract, that can replace the release-family guard after verification.

Missing fields, a non-pong result, malformed versions, booleans/floats/strings in place of the protocol, and negative protocols return `PROTOCOL_ERROR`. A well-formed but unsupported protocol or release returns `UNSUPPORTED_VERSION`. Neither path creates a workspace, pane or Gateway. The supervisor rechecks the live owner each inspection without caching acceptance across upgrades; an unsupported protocol triggers its existing owned-process shutdown. Invalid responses also prevent startup/readiness and use the existing bounded owner-loss cleanup. Pause/Stop retain their local intent and process-safety semantics.

The normal RPC client and the dependency-free recovery popup share the same check. Doctor's `baseline.herdr` now contains `version_range`, `protocols` and `stable_only`; a successful owner check includes the observed `herdr.version` and `herdr.protocol`. Rejections include a locally generated explanation without echoing arbitrary peer text. Hermes remains pinned to commit `b7ac3ba1cdf89f94dfe86de27e01358b194f4053`; its control protocol 1 is unrelated to Herdr protocol 22.

## Source and interface evidence

Reviewed tags: Herdr 0.9.0 at `b99002ac99b09e00b4ca692436cb15a6b0d676f1`, and annotated tag 0.9.1 resolving to `065ef9d6a531c49fb8bee7e818ef837065b21ee9`. Research downloaded 0.9.1 into this repository's ignored `.research` directory and read the existing 0.9.0 reference without modifying it.

| Contract | 0.9.1 source / comparison |
| --- | --- |
| Live pong and protocol 22 | [api/server.rs](https://github.com/herdrdev/herdr/blob/065ef9d6a531c49fb8bee7e818ef837065b21ee9/src/api/server.rs#L342), [protocol/wire.rs](https://github.com/herdrdev/herdr/blob/065ef9d6a531c49fb8bee7e818ef837065b21ee9/src/protocol/wire.rs#L20); both tags report 22 |
| Capability fields | [schema/server.rs](https://github.com/herdrdev/herdr/blob/065ef9d6a531c49fb8bee7e818ef837065b21ee9/src/api/schema/server.rs#L17), byte-identical between these tags |
| Plugin registration and pane opening | [schema/plugins.rs](https://github.com/herdrdev/herdr/blob/065ef9d6a531c49fb8bee7e818ef837065b21ee9/src/api/schema/plugins.rs), byte-identical; `entrypoint`, `placement`, `workspace_id`, `cwd`, `focus`, `env`, `plugin_root` and `enabled` retain their contracts |
| Workspace creation and session snapshot | [schema/workspaces.rs](https://github.com/herdrdev/herdr/blob/065ef9d6a531c49fb8bee7e818ef837065b21ee9/src/api/schema/workspaces.rs), [schema/session.rs](https://github.com/herdrdev/herdr/blob/065ef9d6a531c49fb8bee7e818ef837065b21ee9/src/api/schema/session.rs), byte-identical |
| Pane identity and shell PID | [schema/panes.rs](https://github.com/herdrdev/herdr/blob/065ef9d6a531c49fb8bee7e818ef837065b21ee9/src/api/schema/panes.rs#L527); only an unrelated `PaneLinkRegion` struct was added |
| Response envelopes | [schema/response.rs](https://github.com/herdrdev/herdr/blob/065ef9d6a531c49fb8bee7e818ef837065b21ee9/src/api/schema/response.rs); only the unrelated `PaneLinkResolved` variant was added |
| CLI protocol guard and installer | [cli/protocol_guard.rs](https://github.com/herdrdev/herdr/blob/065ef9d6a531c49fb8bee7e818ef837065b21ee9/src/cli/protocol_guard.rs), [cli/plugin.rs](https://github.com/herdrdev/herdr/blob/065ef9d6a531c49fb8bee7e818ef837065b21ee9/src/cli/plugin.rs#L154); the official installer accepts `--ref` and `--yes` and replaces managed GitHub checkouts |

## Verification

- [Native 0.9.1 evidence](evidence/herdr-0.9.1-compatibility.json): the actual installed binary's SHA-256, live pong and successful plugin RPC/ownership checks. The test used a temporary `/tmp/hgh-native-*` root, dedicated XDG/config/socket/session, `/bin/sh` in non-login mode and disabled update checks. `HGH_TEST_HERDR_BIN` explicitly selected the binary. No real Hermes Profile was configured. The captured server was stopped and the temporary root removed.
- [Full offline output](evidence/release-0.1.3-unittest.txt): Python 3.11 and 3.14, 214 tests each, including patch acceptance, strict handshake validation, rejection before resource creation, live upgrade rechecking, incompatible-protocol cleanup, Doctor and recovery popup coverage. Fixtures now advertise a realistic 0.9.1 / protocol 22 pong. The suite invokes neither installed Herdr nor Hermes.
- [Post-release verification](evidence/release-0.1.3-verification.json): exact main/tag/release CI SHAs, downloaded archive digest and all 808 Git blobs, launcher/version/license checks, and an official isolated 0.1.2 → 0.1.3 installation replacement preserving configuration. The installed code accepts the live 0.9.1 / protocol 22 pong. With no Profile configured, recovery correctly returns `state=ERROR, code=SETUP_REQUIRED`. The default user installation was not upgraded.
- [Release](https://github.com/nocoo/hermes-on-herdr/releases/tag/v0.1.3): immutable tag, source SHA, the four OS/Python CI jobs and verified source archive. Installation and replacement of an existing supervisor follow [the release guide](15-发布与安装.md#升级与回滚).

These checks do not establish native Linux integration, a real Hermes Gateway's online handoff, or message/model round trips. The synthetic future patch versions exercise the policy; they are not claims of testing unreleased Herdr binaries.
