# 18 · Herdr compatibility

Version 0.1.4 uses the JSON API contract and verified pane ownership to decide whether a live Herdr owner can manage the Gateway. It does not pin a Herdr release family or binary wire protocol. Version 0.1.3's `>=0.9.0,<0.10.0` and protocol 22 gates are removed.

## Acceptance contract

The live JSON endpoint must answer `ping` with a result object whose `type` is `pong`. The existing transport still requires a private same-user Unix socket, a matching response ID, bounded response size and a deadline. A malformed envelope or non-pong response is `PROTOCOL_ERROR`.

`version` and `protocol` are diagnostic metadata only. A printable version string of at most 128 characters and an unsigned 32-bit integer protocol are reported by Doctor; absent or malformed metadata is reported as `null`. Neither missing metadata, a newer major/minor release, a prerelease nor a changed wire protocol causes rejection. Unknown fields and capabilities are ignored. This does not claim that every future binary works: each required API response must still satisfy the contract below.

Herdr's `ping.protocol` comes from `protocol::PROTOCOL_VERSION`, which versions its binary terminal/internal transport. This plugin sends newline-delimited JSON directly over the API socket and never implements that binary protocol. Herdr's own CLI checks its compiled protocol against the server; that CLI/server pairing remains Herdr's responsibility and is separate from the plugin's JSON calls. The configured CLI should be upgraded with its server so Hermes' terminal tools continue to work.

Herdr requires `min_herdr_version` in plugin manifests. The manifest keeps `0.9.0` as the earliest researched installation baseline, with no upper bound; it admits 0.10 and 1.x releases. Lowering this baseline would require validating the plugin manifest, actions, hooks and pane API on older Herdr. It is not a runtime 0.9.x restriction.

## Required interfaces and failure behavior

| Interface | Contract used by this plugin |
| --- | --- |
| `plugin.list` | Registered plugin ID, enabled boolean, absolute code root matching the installed plugin |
| `workspace.create`, `plugin.pane.open` | Requested entrypoint, workspace/pane identifiers and ownership metadata; existing creation tickets prevent blind retries after ambiguous responses |
| `pane.get`, `pane.process_info` | Workspace/tab/pane identity, terminal ID, shell PID matching the verified supervisor process |
| `session.snapshot` | Workspace/pane records used to reconcile pending creation |
| Manifest, hooks and environment | Registered actions and pane entrypoints; owner socket/workspace/tab/pane environment; startup and pane lifecycle events |
| `tab.rename`, `pane.rename`, `pane.focus` | Recovery labels and explicit focus; cosmetic rename errors remain best effort |

There is no new capability registry, mutating discovery probe or per-release adapter. Checks run through the existing operations. A successful pong alone never authorizes Gateway startup: plugin registration, pane membership, process identity and Profile exclusivity must also pass. Missing methods or malformed required fields still prevent the dependent operation from proceeding. Failed calls are not automatically retried if they may already have created resources.

The supervisor keeps checking the live owner. A version/wire metadata change with valid API responses leaves the same Gateway running. Loss of required ownership APIs enters UNKNOWN and triggers the existing bounded owner-loss cleanup; confirmed ownership conflicts stop the owned process. Pause/Stop retain their persistent intent and identity-checked process safety.

Normal RPC and the dependency-free recovery popup share the ping check. Doctor reports `baseline.herdr.policy = "json-api-contract"` and observed metadata in the owner check. It does not claim to have exercised all mutating interfaces. Hermes remains pinned to commit `b7ac3ba1cdf89f94dfe86de27e01358b194f4053`; its control protocol 1 is separate from Herdr's protocol.

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

The [216-test suite on both Python versions](evidence/release-0.1.4-unittest.txt) covers future minor/major/prerelease metadata and changed wire protocols, startup and recovery on the same required JSON contract, optional malformed metadata, rejection of non-pong endpoints, missing required APIs before creation, and safe cleanup when a running owner loses `pane.process_info`. Synthetic future versions verify policy, not unreleased Herdr binaries.

The [native validation](evidence/release-0.1.4-native.json) uses an isolated real Herdr 0.9.1 session, dedicated temporary XDG/config/socket directories and no Hermes Profile. It checks registration, workspace/pane creation, ownership and supporting read/rename/focus methods. Release CI runs the offline suite on Ubuntu and macOS with Python 3.11 and 3.14. Native Linux, a real Herdr server upgrade handoff and message/model round trips remain separate validation work.

Historical evidence for 0.1.3 remains in [its release record](evidence/release-0.1.3-verification.json) and [native 0.9.1 checks](evidence/herdr-0.9.1-compatibility.json). These records describe the earlier policy, not the current acceptance rules. Installation and replacement of a supervisor follow [the release guide](15-发布与安装.md#升级与回滚).

[0.1.4 release verification](evidence/release-0.1.4-verification.json) records exact main/tag/release CI, archive verification and isolated official installation. [Local upgrade evidence](evidence/release-0.1.4-local-upgrade.json) records the installed tag and fresh supervisor/Gateway ownership, READY and Discord connection samples; it does not establish a server upgrade handoff or message/model round trip.
