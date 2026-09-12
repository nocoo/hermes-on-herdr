# The Weekend Protocol / 周末交接

Audience: programmers who already work with multiple coding agents. Emotional arc: trust → coordination burden → management → a weekend regained.

The two editions share shot order, frame boundaries, camera paths, geometry, music and transition timing. Voice, captions and on-screen editorial copy are localized. Timing comes from the longer measured language in each chapter; voices are never truncated to fit.

| Shot | Planned minimum | Picture / action | Evidence |
| --- | --- | --- | --- |
| 00 · opening | 3.5 s | Opening ident. Brass door on a machined circular platform. A green signal wakes; camera pushes through the orbit. Product title fills the left. Music sting, no speech. | assets/brand/README.md; assets/brand/source.json |
| 01 · partners | 11 s | Four original terminal panels orbit a central green task signal. Each carries the agent name, a prompt and simple code. No third-party logos. Sequential 12-frame wakeups, camera drifts in. | README.md#使用体验; resources/herdr-control/SKILL.md |
| 02 · management | 10 s | The same panels diverge in depth. Status chips multiply. Amber interruptions cross the task orbit; the green signal hesitates. Large type changes the emphasis from agents to management. | resources/herdr-control/SKILL.md |
| 03 · herdr | 9 s | Panels settle onto one circular chassis. Four clear routes converge on a raised Herdr manager disc; green packets flow in order. Terminal lists workspace and pane identities with illustrative labels. | resources/herdr-control/SKILL.md; docs/02-系统架构.md#22-所有权模型 |
| 04 · weekend | 8 s | An original 3D desk terminal holds Friday 18:00. The circular chassis becomes a clock; a warm sun slips along its arc. Manager keeps running while an empty upper orbit asks for an owner. | README.md; docs/04-Hermes专用Profile设计.md |
| 05 · m2 | 12 s | The brass door returns above Herdr, closing the missing management layer. Camera rises to reveal three levels: Hermes M2, Herdr manager, four agent IC discs. YOU appears as a direction input above the topology. | docs/04-Hermes专用Profile设计.md#42-profile身份与初始化; docs/02-系统架构.md#21-组件图; examples/README.md |
| 06 · control | 10 s | Brass permission ring opens around a floating terminal. Real command forms read agent list, pane read and agent prompt with clearly illustrative pane IDs. A green signal passes through the open door down to the working panel. | docs/07-安全与运维.md#71-当前信任模型; docs/04-Hermes专用Profile设计.md#45-环境继承与credential隔离; resources/herdr-control/SKILL.md |
| 07 · lifecycle | 11 s | Two linked luminous lifecycle rings activate in sync, then dim to an amber paused hold. A small CLI panel shows start, READY, pause, PAUSED, resume. Explicit pause holds across the loop; this is a diagram, not runtime capture. | herdr-plugin.toml; src/hermes_gateway_herdr/supervisor.py; src/hermes_gateway_herdr/lifecycle.py; docs/03-生命周期设计.md |
| 08 · monitor | 15 s | Large perspective panel shows the actual repository demo TUI image, uncropped with preserved aspect. A separate original message panel illustrates a remote status exchange. Small visible labels distinguish demo data and configured messaging. Green signal travels between them. | docs/14-hqtui监控面板.md; docs/evidence/dashboard-two.png; src/hermes_gateway_herdr/dashboard.py; docs/13-cherry接入与验证.md#137-正式-010-发布安装与运行验收; docs/04-Hermes专用Profile设计.md |
| 09 · closing | 10 s | The green signal completes its circle at the brass door. Camera settles; task geometry recedes into an orderly horizon. Native Hexly hexagon and wordmark resolve over a warm cream brand plate with the product door still visible. Hold the final brand and repository URL, no fade to black. | assets/brand/README.md; assets/brand/source.json |

## Narration / 旁白

### opening

**中文**

(Music only / 仅音乐)

**English**

(Music only)

### partners

**中文**

程序员都有自己信任的天才工程师伙伴。 比如 Codex、Grok、Pi，或者 Claude Code。 一个想法，就能和它们一起开工。

**English**

Every programmer has a brilliant engineering partner they trust. Codex, Grok, Pi, or Claude Code. An idea becomes something you can build together.

### management

**中文**

当你有了自己的多 Agent 工作流，真正的问题变成了管理。 谁在推进，谁被阻塞，下一步交给谁？

**English**

Once you have your own multi-agent workflow, the real problem becomes management. Who is progressing, who is blocked, and who takes the next step?

### herdr

**中文**

Herdr 是 manager，负责管理这些天才 IC。 它把工作区、终端和 Agent 状态，组织在一起。

**English**

Herdr is the manager for those brilliant individual contributors. It brings workspaces, terminals, and agent status together.

### weekend

**中文**

可周末到了，你不该还守在电脑前盯着进度。 谁来管理 manager？

**English**

But the weekend is here. You should not have to sit at your computer watching progress. Who manages the manager?

### m2

**中文**

Hermes on Herdr，让当前机器上一个专门、受信任的 Hermes Profile，成为你的 M2。 一个管理 Herdr 的 manager。

**English**

Hermes on Herdr gives that job to a dedicated, trusted Hermes profile on this machine. Your M two: a manager for the manager.

### control

**中文**

这个专用 Hermes 拥有完整 Herdr 控制权限。 读取状态，协调工作，把你的意图传到正在执行的 Agent。

**English**

This dedicated Hermes has full Herdr control. It can inspect status, coordinate work, and carry your instructions to the agents doing it.

### lifecycle

**中文**

允许运行时，它随 Herdr 启动，也随所属会话停止，运行在真实 pane 中。 暂停后，只有明确恢复，才会继续运行。

**English**

When enabled, it starts with Herdr and stops with its session, inside a real pane. A pause stays paused until you explicitly resume.

### monitor

**中文**

打开 monitor TUI，专属实例、多个 Profile、处理器和内存，一眼看清。 通过 Hermes 已配置的消息平台，远程提问，异步跟进。 机器和 Herdr 保持在线，你就可以离开桌面。

**English**

Open the monitor T U I: your dedicated instance, multiple profiles, CPU, and memory in view. Check in remotely and asynchronously through your configured Hermes messaging platform. Keep the machine and Herdr online, and step away.

### closing

**中文**

把天才交给系统管理，把周末还给自己。 Hermes on Herdr，来自 Hexly AI。

**English**

Let the system manage the genius. Keep the weekend for yourself. Hermes on Herdr. By Hexly AI.

## Claims and depiction boundaries

- M2 is the organizational metaphor for a trusted Hermes profile controlling the manager; it is not a separate Herdr role or authorization tier.
- Full Herdr control is deliberate trust on the same OS account, not a restricted sandbox. Setup, credentials, platform allowlists and permissions belong to the operator.
- Lifecycle wording is conditional on persisted running intent; startup does not override PAUSED. Shutdown handling and identity validation are implemented, while cold-boot and platform integration limits remain described in the repository.
- The TUI image is an existing offline demo fixture, not live machine activity. The messaging exchange is an original illustration through a configured Hermes platform, not a recorded end-to-end test.
- The machine and its Herdr session must remain running and connected for remote work. The plugin does not host work in a new cloud service.
- Initial profile creation/selection wizard is not advertised; current setup is manual configuration and explicit bind/start.
