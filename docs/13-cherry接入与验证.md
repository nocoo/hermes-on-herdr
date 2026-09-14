# 13 · cherry 接入与验证

2026-09-11 建立，2026-09-14 更新。目标是移除 `cherry` 的 Gateway 系统自启动，由默认 Herdr session 中的本插件负责启动与监管，并验证正常消息处理和 Herdr 双向交互。

**13.1–13.6 是首次开发 link 接入的历史记录，不表示当前运行状态。** 当时 cherry 在插件监管下达到 READY，用户确认消息连通，90 项离线测试通过。用户重启 Herdr 后，首次 startup hook 因原生 PID 文件权限被拒绝；两处兼容性问题修复后，通过手动 `ensure` 恢复。真实 pane 归属、进程身份、单实例和 Discord 连接已核对，原生 LaunchAgent 保持移除。修复后的完整冷启动、退出清理及指定 pane 双向交互仍需各自的真实验收。

**正式 0.1.0 安装后的运行证据见 13.7。** 已用 Herdr 官方安装器替换开发 link，cherry 在发布版本下达到 READY，嵌入终端监控和独立网页健康面板均已运行。

**0.1.1 的升级与运行观察见 13.8。** 该次记录包含升级前的 ORPHAN、升级后一次 UNKNOWN 退出及核验后的恢复；退出根因尚未定位，不能把恢复运行当作修复。

**0.1.2 的发布与隔离安装验证见 13.9，本机正式升级及运行验收见 13.10。** 发版时保留了正在运行的 cherry；随后按用户要求切换到正式 tag，并重建 supervisor。

## 13.1 实际观察

以下为原生 Gateway 停服前的基线；停服结果见 13.4。

| 项目 | 结果 |
|---|---|
| Profile | 已有 `cherry`，目录 `~/.hermes/profiles/cherry`，0700 |
| 原启动来源 | `ai.hermes.gateway-cherry` LaunchAgent，RunAtLoad/KeepAlive 均为 true |
| 原进程 | wrapper PID 44324，Gateway PID 44325；已记录 OS 创建时间和 SID |
| 真实控制协议 | identify/status 响应的 Profile、home、PID/start、固定 SHA 一致 |
| 消息平台 | Discord connected；platform writer 身份与回答的 Gateway 一致 |
| 当前工作 | 采样时 active_agents=0；切换前仍需重新检查 |
| 模型 | 原有 custom provider 和模型配置保留；未发起新模型请求 |
| Herdr | 已安装 0.9.0；默认 server 的 ping 和 snapshot 可读，现有 11 个 workspace |
| Hermes | `b7ac3ba1cdf89f94dfe86de27e01358b194f4053`；tracked 源码干净，保留既有 untracked 文件 |
| 插件注册 | `nocoo.hermes-gateway` 指向本仓库，enabled=false；原有插件保留 |

上述 healthy 是原 LaunchAgent 实例的历史基线；插件监管下的运行结果见 13.5。

## 13.2 已准备的配置和备份

- 插件配置：`~/.config/herdr/plugins/config/nocoo.hermes-gateway/config.json`，绑定默认 Herdr socket 和 `cherry`，expected_platforms 为 `discord`。
- 配置目录 0700，config.json/runtime-python 0600；Python 使用现有 Hermes venv。Profile 已绑定到上述默认 session，控制目录为 `~/.hermes/profiles/cherry/.herdr-gateway-herdr/`。
- Homebrew 的 bin/Cellar 父目录为组可写，不能通过本插件的 executable 路径预检。已把同一份 0.9.0 二进制复制到插件私有 `bin/herdr`，验证版本和 SHA-256 与来源相同；Homebrew 目录权限未修改。
- 原 config.yaml、.env、SOUL.md 和 LaunchAgent plist 备份在本机私有目录 `~/.local/state/hermes-gateway-herdr/cherry-20260911T123729Z/`。候选文件位于其 `prepared/` 子目录；config.yaml、SOUL.md 和 Herdr skill 已于 2026-09-12 应用到 cherry。
- 应用前核对原配置与备份 hash；应用后核对候选文件 hash，并再次通过实际 Profile 预检和固定安装版本检查。`.env` 未重写，内容仍与备份完全一致。

已应用的配置差异：

| 字段/文件 | 已应用内容 |
|---|---|
| terminal | local backend；HOME 按 Profile；cwd 为 cherry/workspace；关闭自动 shell 初始化 |
| gateway.multiplex_profiles / multiplex_profiles | false |
| nous.keepalive_interval_seconds | 0 |
| platform_toolsets.discord | terminal、skills、memory |
| agent.disabled_toolsets | 增加 cronjob、browser、file |
| SOUL.md | 保留原文，追加 Herdr 控制入口说明 |
| skills/herdr-control/SKILL.md | 安装本仓库的 [Herdr 控制 skill](../resources/herdr-control/SKILL.md) |

Discord 工具集已从原通用工具集收窄到表中三类。模型配置、custom provider 定义及 .env 内容保持原值。

## 13.3 已完成的代码修复与测试

真实配置使用 `model.api_key: '${ENV_NAME}'` 引用 Profile 的 .env。原预检把任何 api_key 字段均视为内嵌秘密，导致这种 Hermes 标准格式也被拒绝。

- `3876f8e`：只允许严格的字面 `${NAME}` 引用；仍拒绝明文密钥、插值后缀、shell 表达式和非字符串。预检不解析秘密、不写 Profile。
- `6267d1c`：增加有范围约束的 Herdr 交互 skill，要求实际 ID、指定目标、无焦点创建和结果回读。
- 新回归用例在修复前失败；修复后配置测试 9 项通过。
- 全套实际执行：`/Users/nocoo/.hermes/hermes-agent/venv/bin/python -I -B tests/run.py`，**86 项通过，14.183 秒，退出码 0**。这是离线 fixture 测试；原 84 项历史完整输出仍保存在 [12](12-离线实现与验证.md)。

2026-09-12 新增启动准备测试，原子提交 `dfe9292`：禁用插件时执行 `start` 只持久化 running，不创建 pane 或 Gateway；启用后的 startup hook 启动一个受控假 Gateway，重复 hook 保持同一个实例。新增用例通过，全套再次实际执行：**87 项通过，15.094 秒，退出码 0**。测试仍使用离线 fixture，没有启动真实 cherry。

用户重启后的真实检查暴露两处与固定 Hermes 版本的兼容性问题，分别原子提交：

| 提交 | 原因与修复 | 回归证明 |
|---|---|---|
| `17d6fb0` | Hermes 创建 `gateway.pid` 时未传 mode，默认 0777 在子进程 umask 0077 下得到 0700；旧 PID 已退出仍会在读取前被拒绝。仅原生 PID 元数据读取允许 owner execute；其他文件读取保持严格 0600 | 0700 元数据仍阻止匹配的活进程，陈旧身份可放行；内容、inode、权限不变。公共权限、软硬链接继续拒绝，通用私有读取仍拒绝 0700 |
| `8f9db0f` | Hermes 的 psutil 时间戳为 `int(round(create_time * 100))`，原匹配使用截断。改为完全一致的舍入，保留 Linux ticks 支持，不增加容差 | 覆盖 `1234.564 → 123456`、`1234.566 → 123457`、相邻厘秒拒绝及 Linux ticks/psutil 回退；假 Gateway 同步原生格式 |

两项回归均先观察到失败，再完成修复。权限修复后全套 **89 项通过，14.340 秒**；时间戳修复后使用上述隔离命令实际执行，全套 **90 项通过，14.611 秒，退出码 0**。这些测试仍为离线 fixture；真实运行证据另见 13.5。

## 13.4 已完成的接入与重启准备

2026-09-12，用户明确要求先停止 cherry，并移除原生 Gateway 的 launchd 管理。已执行：

- 停服前重新核对 Profile、固定 SHA、PID/start、父子进程关系，以及配置和 plist 的备份 hash；实时 `active_agents=0`。
- 为已验证的 Gateway PID 44325 写入原生 planned-stop 标记，执行 `launchctl bootout gui/501/ai.hermes.gateway-cherry`，退出码 0。
- 确认 wrapper 44324 和 Gateway 44325 均已退出、launchd 中找不到该服务后，移除 `~/Library/LaunchAgents/ai.hermes.gateway-cherry.plist`；原文件备份保留。
- 退出后第 0、10、30 秒检查均无 cherry Gateway 进程、无控制 socket、无已加载的 LaunchAgent，plist 保持不存在。原生运行状态为 `stopped`。
- `gateway.lock` 未被删除或替换，inode 仍为 41887302，已验证没有进程持锁；原生停服阶段保留了原权限 0644。
- 原生停服阶段结束时 Herdr ping 正常；插件仍 disabled，未创建 binding、应用候选配置或启动替代实例。

本机私有证据：`~/.local/state/hermes-gateway-herdr/cherry-20260911T123729Z/native-stop-20260911T205737Z.json`。以上证明原生服务已退出且观察期间没有复活；该阶段尚未验证 Discord 客户端显示及插件监管能力。

随后用户要求配置好插件，并准备自行重启 Herdr。已完成：

1. 再次核验原生进程、PID/socket 和 LaunchAgent 均不存在；核对原配置与备份后，应用 13.2 中的 config、SOUL 追加段和 skill。
2. 持有原 `gateway.lock` 的排他锁期间完成配置替换，并把锁权限收紧为 0600；inode 仍为 41887302，随后释放锁。
3. 通过实际 CLI 执行 `bind --dry-run` → `bind --apply`，确认初始 paused。插件保持禁用时执行 `start`，返回 `DISABLED`、`desired=running`、revision=1；此步骤没有创建 Gateway。
4. 执行 `herdr --session default plugin enable nocoo.hermes-gateway`。实际 registry 和在线查询均为 enabled=true，其他插件记录保持一致；startup 入口为 `ensure --source startup`。
5. 通过真实 Herdr action 执行 Doctor，日志 `plugin-log-944` 为 succeeded、exit_code=0、stderr 为空，Profile、Hermes 版本和 owner 三项检查全部通过。
6. 重启前核对为 `ABSENT`、`desired=running`、revision=1，无 pending/runtime、无持锁 supervisor、无 fuse；原生 LaunchAgent 未恢复。

本机私有接入证据：`~/.local/state/hermes-gateway-herdr/cherry-20260911T123729Z/plugin-setup-20260911T210343Z.json`，包含配置 hash、原插件 registry、绑定、运行意图和 Doctor 结果。

重启交接时给用户的命令为：在 **Herdr 外部终端**执行第一条，等默认 session 的 Herdr 退出后再执行第二条：

```sh
herdr --session default server stop
herdr --session default
```

这会重启后台 server，影响该 session 内的工作任务；Agent 未执行这两条命令，随后用户反馈已重启。只关闭并重开 TUI 可能重新连接到原 server，不能据此证明冷启动。插件也响应 `workspace.focused`，因此应分别记录重启前后的实例；本次观察见 13.5。

重启后的核验范围为真实 pane IDs、Gateway 与 supervisor 身份及 SID、单实例、两次新鲜平台观察、Discord 消息和指定 pane 双向交互。任何进一步由 Agent 执行的 Stop/Restart/Pause/Herdr 停服均需获得对应确认。

## 13.5 重启检查与三项目标的验收

2026-09-12，用户反馈重启完成后检查：新 Herdr server PID 94384 正常响应，版本 0.9.0；`plugin-log-1` 中 `ensure --source startup` 以退出码 20、`UNSAFE_PATH` 失败。此前一代 supervisor PID 93348 和 Gateway PID 93380 均已退出，账本记录 Gateway 退出码 -1（SIGHUP），运行意图仍为 running；旧实例还曾出现 `GATEWAY_IDENTITY`。两项原因及修复见 13.3。

确认旧进程均已退出、Profile 未被占用后，执行 `ensure --source manual`，沿用 running/revision=1。首次返回 PENDING，随后达到 READY。恢复后独立读取原生 identify/status 两次，间隔约 1.1 秒，第二次达到 readiness level 2；没有执行新的停服或 Herdr 重启。

| 检查项 | 恢复后的实际结果 |
|---|---|
| 运行意图 | running；intent_revision=applied_revision=1；未熔断，无 last_exit |
| generation | `f5aa5a187b9f4350b0a08eaecb98874f` |
| 进程身份 | supervisor PID 99562，Gateway PID 99566；实时 OS 身份与账本一致，Gateway PPID=99562，二者 SID=99562 |
| 真实 pane | workspace `w20`、tab `w20:t3`、pane `w20:p3`；Herdr API 确认 pane 的 shell_pid 为 supervisor |
| 环境 | Gateway 的 HERMES_HOME 和 HERDR_SOCKET_PATH/WORKSPACE_ID/TAB_ID/PANE_ID 均与配置及实时归属匹配 |
| 单实例 | lifetime lock 被持有；同用户 Gateway 进程扫描只找到一个 cherry 实例，PID 99566 |
| 原生探针 | 两次回答身份均为 cherry、固定 Hermes SHA、supervisor=external；Discord connected，采样 active_agents=0，第二次观察为 READY |
| 原生自启动 | LaunchAgent 未加载，原 plist 不存在 |

提供给用户的 Discord 测试要求回复唯一标记 `CHERRY-CHECK-20260912-A1`，并通过 Herdr skill 读取当前 session、报告自身 workspace/tab/pane IDs。用户回复“通的，测过了”，记为**用户确认消息连通**；未独立留存完整回复或比对其中的 IDs，也未捕获指定 pane 写入、回读、Discord 回报的完整链路。

本机私有证据：`~/.local/state/hermes-gateway-herdr/cherry-20260911T123729Z/restart-check-20260911T211626Z.json`。保留首次 startup 失败记录，并追加 recovery，包含修复提交、90 项测试结果、真实进程/环境/归属、两次新鲜原生观察及用户确认。

| 用户目标 | 验收方式 | 当前结果 |
|---|---|---|
| 随 Herdr 生命周期启停 | 默认 session 冷启动自动产生一个受监管 Gateway；停止 server 后该 Gateway 退出；再次启动重新就绪。记录 PID/start/SID、意图、pane IDs 和实例数 | PARTIAL；首次 startup 失败，修复后手动 ensure 达到 READY；修复后的冷启动和当前一代退出清理待测 |
| cherry 正常工作 | 插件监管下 Discord connected；实际用户消息触发模型并得到带唯一标记的回复 | PASS（用户确认消息连通）；原生探针独立确认 Discord connected，未留存完整消息回复 |
| 读取 Herdr 并双向交互 | Discord 发指令 → cherry 读取真实 snapshot → 在明确的测试 pane 操作 → 回读新的终端结果 → Discord 回报；用独立核查比对实际输出 | PARTIAL；真实环境注入和 pane 归属已核对；指定 pane 的双向操作链路尚未独立验证 |

重复 ensure 不新增进程、暂停不复活、restart 保持 supervisor 等离线断言仍需在真实运行中补证。当前不能承诺自动孤儿回收；UNKNOWN/ORPHAN 必须阻止替代启动并保留证据。

## 13.6 回滚顺序

获得需要的停服确认后，先持久 Pause，并核验插件 Gateway/已确认后代确已退出，再 disable 插件。恢复本次修改的 config/SOUL；新增 skill 只有 hash 仍匹配本次安装时才移除。恢复原 plist 并 bootstrap 原 LaunchAgent，重新检查原 cherry 的身份、Discord 连接和消息回复。

如果进程归属或退出结果不明，保持暂停并核验现场，不并行拉起旧 LaunchAgent。保留 Profile 历史、会话及凭据；私有备份和运行数据不提交 Git。

## 13.7 正式 0.1.0 发布、安装与运行验收

2026-09-12，本次工作获准完成发布、官方安装和 cherry 接管。接手时 `ai.hermes.gateway-cherry` 及其 plist 已在前一阶段移除，开发版 supervisor 也已退出；状态为 ABSENT、desired=running。此次没有再次停用一个在线的原生 cherry 服务，而是核验现场后把开发 link 换成正式安装并恢复运行。独立的 default Profile 仍由 `ai.hermes.gateway` 管理，不属于本次停服范围。

发布记录：

| 项目 | 实际结果 |
|---|---|
| 正式 Release | [hermes on herdr 0.1.0](https://github.com/nocoo/hermes-on-herdr/releases/tag/v0.1.0)，2026-09-12 01:46:03 UTC 发布，非 draft、非 prerelease |
| annotated tag / commit | `v0.1.0` → `99f30d8c2eed209d827c70e5f8a6c819a157fad2` |
| 发布前 main CI | [34665421329](https://github.com/nocoo/hermes-on-herdr/actions/runs/34665421329)，head SHA 为上述 commit；Ubuntu 24.04 / macOS × Python 3.11 / 3.14 四项均 success |
| tag CI | [34665598551](https://github.com/nocoo/hermes-on-herdr/actions/runs/34665598551)，相同 head SHA；四项均 success，四项 tag/version 检查均通过 |
| 本机完整回归 | Python 3.11 和 3.14 各 167 项通过，另有 400 次真实 macOS 退出检查；[完整测试输出](evidence/release-0.1.0-unittest.txt) |
| Release 附件 | `hermes-on-herdr-0.1.0.tar.gz`，16,329,936 bytes；另附 `SHA256SUMS`。已重新下载并验证摘要、归档路径、launcher 执行权限、旧 launcher symlink、manifest 版本和 vendor MIT 声明 |
| 归档 SHA-256 | `80217d427dfbfe44eabea65f43ffae8fccf3cb22786cbf2b2416b9286d9b0e80`；解压后的 launcher 实际报告 `hermes-on-herdr 0.1.0` |

先持久化 paused/revision=2，核验没有 cherry Gateway、supervisor 或持锁实例，再禁用并 unlink 开发插件，退出旧独立监控。随后成功执行官方安装命令：

```sh
herdr --session default plugin install nocoo/hermes-on-herdr --ref v0.1.0 --yes
```

Herdr 返回的安装根目录为 `/Users/nocoo/.config/herdr/plugins/github/nocoo.hermes-gateway-83b783d49cce`。注册记录为 enabled=true、version=0.1.0、source.kind=github、requested_ref=v0.1.0、resolved_commit=上述完整 SHA；安装 checkout 的 HEAD 一致，工作树干净。安装器获取的是 Git tag，Release 附件另行核验。

私有配置 `~/.config/herdr/plugins/config/nocoo.hermes-gateway/config.json` 只更新 `plugin_root`，保留原有 cherry/owner 绑定。实际执行 `bind --dry-run`、`bind --apply` 和 Doctor 均通过，paused 意图未被安装自动启用覆盖。运行环境沿用 Hermes v0.21.1 的固定 SHA 与私有 Herdr 0.9.0 二进制。再次检查 Profile 占用、锁和原生服务后才显式 Start，得到 running/revision=3；没有删除或替换原生锁来绕过占用检查。

以下为 **2026-09-12 09:55（UTC+8）** 的真实运行快照。验证代码从已安装 checkout 导入；原生 identify/status 独立读取两次，间隔超过 1.1 秒，第二次达到 readiness level 2。

| 检查项 | 实际证据 |
|---|---|
| 进程归属 | Herdr server PID **94384** → supervisor PID **4854** → Gateway PID **4888**；Gateway PPID=4854，Gateway 和 supervisor SID=4854 |
| OS 创建时间 | supervisor `1789177943.42964`，Gateway `1789177943.652646`；与运行账本身份一致 |
| 已安装代码 | supervisor argv 指向上述安装目录的 `src/hermes_gateway_herdr/__main__.py`；Gateway argv 为 `hermes -p cherry gateway run --external-supervisor` |
| 真实 pane | workspace `w32`、tab `w32:t2`、pane `w32:p2`；Herdr process-info 的 shell_pid=4854 |
| 单实例 | 同用户进程扫描只找到 cherry Gateway **4888**；lifetime lock 被持有；default Gateway **1149** 的 PID/start 与接手基线一致 |
| 插件 / supervisor | READY、desired=running、intent_revision=applied_revision=3；直接 supervisor status 报告 profile=cherry；无 fuse、无 last_exit |
| generation | `68991929a6dc4c4eba04a56310cdd60c` |
| 环境与原生身份 | HERMES_HOME 与 cherry 目录一致，四个 HERDR 字段与 owner/pane 一致；identify 的 profile=cherry、supervisor=external、Hermes SHA 为固定版本 |
| Discord 平台 | 两次新鲜 status 均 connected，writer_pid=4888、writer_start_time=178917794365 与已核验 Gateway 一致；needs_attention=false，采样 active_agents=0 |
| 终端监控 | supervisor 的唯一嵌入 renderer PID **4885**；在 `w32:p2` 按 Enter 后实际回读到 `LIVE 2/2 online`、cherry READY、`v0.1.0` 和 `q Status` |
| 网页监控 | Herdr pane `w2X:p2` 内运行已安装版本，HTTP listener PID **5067**；`http://127.0.0.1:8767/` 返回 HTTP 200 / text/html |
| 健康检查 | `http://127.0.0.1:8767/health` 返回 **HTTP 200**，healthy=true、profile=cherry、state=READY、gateway_pid=4888、pane=w32:p2、discord=connected，采样年龄 0.88 秒 |
| 原生重复实例 | `launchctl print gui/501/ai.hermes.gateway-cherry` 找不到服务，`~/Library/LaunchAgents/ai.hermes.gateway-cherry.plist` 不存在 |
| 配置保全 | config.yaml、.env、SOUL.md 和 Herdr skill 字节与此次安装前备份一致；其他插件注册记录一致；default Profile 继续在线 |

网页面板实际启动命令：

```sh
/Users/nocoo/.config/herdr/plugins/github/nocoo.hermes-gateway-83b783d49cce/bin/hermes-on-herdr --config /Users/nocoo/.config/herdr/plugins/config/nocoo.hermes-gateway/config.json dashboard --http-port 8767
```

只读取 Start 前记录的日志偏移之后的内容，捕获到本次连接：

```text
2026-09-12 09:52:30,578 INFO hermes_plugins.discord_platform.adapter: [Discord] Connected as cherry#5217
```

本机私有证据保存在 `~/.local/state/hermes-gateway-herdr/release-0.1.0-20260912T013522Z/`，包括安装前基线、Start 回执、`live-evidence.json` 和 `terminal-monitor.txt`。配置、凭据和原始完整 Gateway 日志未提交 Git。

本次独立证明了正式安装来源、运行归属、单实例、Discord 重新连接及两种面板运行。**没有发起新的消息/模型往返**，13.5 的用户反馈仍属于上一阶段；完整 Herdr 冷启动/退出清理、Herdr 在线升级 handoff、指定 pane 双向消息操作及 Linux 真实 Herdr 接入仍待验证。网页面板仅绑定本机，单独启动，不是自动安装的系统服务。发布 tag 保持固定；本节为发布后的运行记录，不修改已发布源码。

## 13.8 0.1.1 升级与运行观察

2026-09-12，按用户要求发布补丁版并升级本机插件。[Release 0.1.1](https://github.com/nocoo/hermes-on-herdr/releases/tag/v0.1.1) 的 annotated tag 固定到 `1b81de6a6f9530fac8602ee98f345cebaf51b7cd`。本节与[结构化验证记录](evidence/release-0.1.1-verification.json)是发布后的观察，不移动 tag。

- Python 3.11.15 / 3.14.7 本机各 **186 项通过**，[发版测试输出](evidence/release-0.1.1-unittest.txt)。[main CI](https://github.com/nocoo/hermes-on-herdr/actions/runs/34686759627) 和 [tag CI 第二轮](https://github.com/nocoo/hermes-on-herdr/actions/runs/34686872134/attempts/2) 的四个 OS/Python 组合均通过，SHA 与 tag 一致；[Release workflow](https://github.com/nocoo/hermes-on-herdr/actions/runs/34687080630) 校验来源、打包和发布成功。
- tag CI 首轮的 macOS / Python 3.11 并发启动用例触发五秒 fixture 等待超时。[同一用例连续 20 次本机复测](evidence/release-0.1.1-recheck.txt)全部通过，随后完整 tag 矩阵通过。未修改源码、断言或 deadline；[首轮失败](https://github.com/nocoo/hermes-on-herdr/actions/runs/34686872134/attempts/1)保留，未在本机复现其原因。
- Release 附件重新下载后，SHA-256、全部 **791 个 Git blob**、路径、launcher 执行权限、兼容 symlink、版本及 vendor 许可均通过核验；两个解压 launcher 均报告 `0.1.1`。源码包 122,799,593 bytes，SHA-256 为 `da9e0277e314dd4e73f7aae5b9c979ac5fd6a8f10539fe178ad4ff05d471cc0f`；不含生成的 MP4/音频。

升级前，0.1.0 的 supervisor 已不存在，cherry Gateway PID 4888 成为 ORPHAN。独立核对其原账本指纹、argv、原生 identify/status、Profile 和固定 Hermes SHA，采样 active_agents=0、无后代。先备份并用 Stop 持久化 paused/revision=4；该命令正确报告 ORPHAN 和未完成。随后只向已核验的孤儿及旧网页监控 PID 5067 发送 SIGTERM，确认退出、无 Profile 占用、lifetime lock 释放且状态为 PAUSED，才禁用插件并安装。

官方安装命令为 `herdr --session default plugin install nocoo/hermes-on-herdr --ref v0.1.1 --yes`。列表记录 enabled=true、version=0.1.1、source.kind=github、requested_ref=v0.1.1、resolved_commit=上述 SHA；实际 checkout HEAD 一致且工作树干净。`plugin_root` 未移动，配置无需重写。新版 Doctor 的 Profile、Hermes 版本和 owner 检查通过后，显式 Resume 保存 running/revision=5。

首次新版 supervisor PID 39198 / Gateway PID 39222 曾达到 READY，随后 supervisor 在 **10:01:59 UTC** 记录 `supervisor_error / UNKNOWN` 并退出；之后确认二者均已不存在。Herdr server PID 94384 一直运行，独立网页监控当时尚未重开。日志没有足以定位根因的调用栈。确认无活进程和持锁实例后，使用同一已发布代码执行 `ensure --source manual` 恢复，未改变 running 意图或创建重叠实例。

恢复后连续观察 **90 秒、767 个采样**，进程身份与后代检查未再报错，状态保持 READY。后续现场核验为 supervisor **39901** → Gateway **39907**，pane **w35:p3**；Gateway PPID/SID、真实 pane shell PID、Profile 和五个 Hermes/Herdr 环境字段全部匹配。两次间隔超过 1.1 秒的原生探针确认 Discord connected，第二次达到 level 2。网页监控在原 pane **w2X:p2** 重开，`/health` 返回 **200 / healthy=true / version=0.1.1**；实际终端与网页均显示 v0.1.1。精确采样时刻见结构化记录。

插件配置、cherry 的 config.yaml、.env、SOUL 和 Herdr skill 字节均保留；其他插件注册及 default Gateway 的进程指纹一致。Agent 没有删除或替换原生锁。Hermes 自身会在启动前清理未占用的陈旧 PID/lock，因此不把跨运行的 inode 相等作为验收条件；已核验当前 0600 锁被持有、锁内 PID/start 与新 Gateway 一致，且观察期间 inode 未变。依据为固定上游 [status.py](https://github.com/NousResearch/hermes-agent/blob/b7ac3ba1cdf89f94dfe86de27e01358b194f4053/gateway/status.py) 的 `get_running_pid` / `_cleanup_invalid_pid_path`。

本机私有备份与原始证据位于 `~/.local/state/hermes-gateway-herdr/release-0.1.1-20260912T094546Z/`，包含配置备份、Stop/Resume 回执、退出确认、90 秒观察和最终现场核验。**UNKNOWN 退出根因仍未定位。** 当前 READY 和短时观察不是长期稳定性证明；本次没有完成新消息/模型往返、整个 Herdr 冷启动/退出、Linux 真实接入或 Herdr 二进制升级 handoff。新版已通过重建 supervisor 生效，完整宿主重启仍由用户选择合适时机执行。

## 13.9 0.1.2 发布与隔离安装验证

2026-09-14，[Release 0.1.2](https://github.com/nocoo/hermes-on-herdr/releases/tag/v0.1.2) 发布常驻 Dashboard、启动／重试按钮、独立恢复中心和持久恢复提示，并将 Hermes 自身插件选择交回 Hermes。annotated tag 固定到 `5ca4fe349fc592d052a58f0a65bd5bf2afc74931`；本节与[结构化记录](evidence/release-0.1.2-verification.json)为发布后的验证记录，不移动 tag。

- [main CI](https://github.com/nocoo/hermes-on-herdr/actions/runs/34793490140) 和 [tag CI](https://github.com/nocoo/hermes-on-herdr/actions/runs/34793615909) 均在该 SHA 首轮通过四个 OS/Python 组合，每组 **206 项测试**；[Release workflow](https://github.com/nocoo/hermes-on-herdr/actions/runs/34793720083) 校验、打包和发布成功。
- 重新下载源码附件后，SHA-256、全部 **800 个 Git blob**、归档路径、launcher 执行权限、兼容 symlink、版本与 vendor 声明均通过。两个解压入口均报告 `hermes-on-herdr 0.1.2`。源码包 122,842,642 bytes，SHA-256 为 `655f799a78e4fc25555dccfd6440242001436197e634e62b29021c58fbaf75f4`，与 GitHub 附件摘要一致。
- 在独立 XDG 目录、socket 和 Herdr 0.9.0 session 中执行官方 `plugin install nocoo/hermes-on-herdr --ref v0.1.2 --yes`，核对 GitHub 来源、requested_ref、resolved_commit、enabled 和干净 checkout。无 Profile 配置时，恢复入口显示 SETUP_REQUIRED，原生 Recovery action 和 popup 均已注册；测试结束后已关闭隔离 server。该安装检查没有启动真实 Hermes Gateway。

本次发版没有重启本机 Herdr 或 cherry。最终只读检查为 READY、Discord connected，supervisor **24128** → Gateway **24137**，pane **w35:p5**，running 意图 revision **5**；进程身份、generation 和意图与发版前一致。发版验证时，本机注册仍为 `v0.1.1`，包含此前开发阶段安装的源码更新；**本次没有把本机正式安装切换为 `v0.1.2`，也没有重建 supervisor 加载新版本**。隔离安装成功不能代替本机升级验收。

恢复 UI、原生 popup 与标签在隔离 server 冷恢复后的检查见[恢复验证](evidence/recovery-validation.txt)。本机 Python 3.11 / 3.14 各 206 项代码回归通过；更新版本号后另重跑两个环境的版本／manifest 检查。此前偶发 FIFO CLI 超时在上述本机回归和两轮发布 CI 中均未复现，根因仍未定位。完整真实 Herdr 生命周期、电脑重启、Linux 原生安装、在线升级 handoff 和新消息／模型往返仍未验证。

## 13.10 本机切换正式 0.1.2

2026-09-14，按用户要求使用 Herdr 原生安装器，将本机 cherry 从包含开发更新的旧 checkout 切换到正式 `v0.1.2`。安装来源为 GitHub，resolved_commit 与发布 tag 一致：`5ca4fe349fc592d052a58f0a65bd5bf2afc74931`。实际安装目录未变，checkout 干净且插件已启用。[结构化验证记录](evidence/release-0.1.2-local-upgrade.json)记录最终状态与检查范围。

升级前已备份私有配置、控制状态、Profile 配置及 skill、旧 checkout 的修改补丁和未跟踪文件。原生探针显示 active_agents=0；Stop 将意图从 running/revision=5 保存为 paused/revision=6，并确认 Gateway 已停止。随后禁用插件，核验 pane 与 supervisor 归属，只关闭旧专用 pane `w35:p5`。旧 supervisor 24128、renderer 24134 和 Gateway 24137 全部退出，lifetime lock 释放、Profile 不再占用后，才安装正式 tag；没有删除或替换原生锁。

新版通过 Doctor 的 Profile、Hermes 版本和 owner 检查后，使用 expected_revision=6 的 Resume 恢复运行，意图变为 running/revision=7。新 supervisor **11815** → Gateway **11819** 位于专用 pane **w35:p6**；实际 pane shell PID、Gateway 的 PPID/SID、Profile 与 Herdr 控制环境均匹配。两个间隔 1.2 秒的原生探针确认 Discord connected，第二次达到 READY。真实终端 Dashboard 显示 **v0.1.2**，无参数恢复命令 `hermes-on-herdr` 的诊断也为 READY，恢复 tab/pane 标签已写入 Herdr 的 session 快照。随后 30.104 秒、11 次采样均保持同一 generation 的 READY；这次观察不代表长期稳定性证明。

Herdr server **4433**、用户工作 pane **w35:p4**、其他 Gateway **1239** 及其他插件注册均保持不变；升级期间没有重启 Herdr server。354 个静态配置及 skill 文件的字节校验一致，包括插件配置、Profile 的 config.yaml、.env 和 SOUL。Hermes 的动态 `skills/.usage.json` 发生更新，保留其现有运行记录。私有备份位于 `~/.local/state/hermes-on-herdr/backups/20260914-official-012-005740-cy86zd3z/`。本次没有发起新消息／模型往返，也没有执行整个 Herdr server 或电脑重启。
