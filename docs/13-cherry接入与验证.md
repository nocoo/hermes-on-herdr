# 13 · cherry 接入与验证

2026-09-11 建立，2026-09-12 更新。目标是移除 `cherry` 的 Gateway 系统自启动，由默认 Herdr session 中的本插件负责启动与监管，并验证正常消息处理和 Herdr 双向交互。

**cherry 在插件监管下为 READY，用户已确认消息连通，90 项离线测试通过。** 用户重启 Herdr 后，首次 startup hook 因原生 PID 文件权限被拒绝；两处兼容性问题修复后，通过手动 `ensure` 恢复。真实 pane 归属、进程身份、单实例和 Discord 连接已核对，原生 LaunchAgent 保持移除。修复后的冷启动、退出清理及指定 pane 双向交互仍待验证；后续由 Agent 执行停服仍需先确认。

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
