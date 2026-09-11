# 13 · cherry 接入与验证

2026-09-11。目标是移除 `cherry` 的 Gateway 系统自启动，由默认 Herdr session 中的本插件负责启动与监管，并验证正常消息处理和 Herdr 双向交互。

**当前仅完成接入准备。插件已注册为 disabled；原 cherry Gateway 和 Herdr 仍在运行。用户要求任何停服操作先确认。** 下列待执行步骤不能当作真实集成 PASS。

## 13.1 实际观察

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

当前 healthy 是原 LaunchAgent 实例的基线，尚未证明它在本插件监管下能启动或完成业务往返。

## 13.2 已准备的配置和备份

- 插件配置：`~/.config/herdr/plugins/config/nocoo.hermes-gateway/config.json`，绑定默认 Herdr socket 和 `cherry`，expected_platforms 为 `discord`。
- 配置目录 0700，config.json/runtime-python 0600；Python 使用现有 Hermes venv。
- Homebrew 的 bin/Cellar 父目录为组可写，不能通过本插件的 executable 路径预检。已把同一份 0.9.0 二进制复制到插件私有 `bin/herdr`，验证版本和 SHA-256 与来源相同；Homebrew 目录权限未修改。
- 原 config.yaml、.env、SOUL.md 和 LaunchAgent plist 备份在本机私有目录 `~/.local/state/hermes-gateway-herdr/cherry-20260911T123729Z/`。候选文件位于其 `prepared/` 子目录，均未应用到当前 Profile。
- 候选配置通过结构/策略预检和固定安装版本检查；最终对照确认现有四份文件与备份 hash 一致。

候选配置差异：

| 字段/文件 | 拟应用内容 |
|---|---|
| terminal | local backend；HOME 按 Profile；cwd 为 cherry/workspace；关闭自动 shell 初始化 |
| gateway.multiplex_profiles / multiplex_profiles | false |
| nous.keepalive_interval_seconds | 0 |
| platform_toolsets.discord | terminal、skills、memory |
| agent.disabled_toolsets | 增加 cronjob、browser、file |
| SOUL.md | 保留原文，追加 Herdr 控制入口说明 |
| skills/herdr-control/SKILL.md | 安装本仓库的 [Herdr 控制 skill](../resources/herdr-control/SKILL.md) |

Discord 工具集会从当前通用工具集收窄到表中三类，这是切换方案的一部分。模型配置、custom provider 定义及 .env 内容保持原值。

## 13.3 已完成的代码修复与测试

真实配置使用 `model.api_key: '${ENV_NAME}'` 引用 Profile 的 .env。原预检把任何 api_key 字段均视为内嵌秘密，导致这种 Hermes 标准格式也被拒绝。

- `3876f8e`：只允许严格的字面 `${NAME}` 引用；仍拒绝明文密钥、插值后缀、shell 表达式和非字符串。预检不解析秘密、不写 Profile。
- `6267d1c`：增加有范围约束的 Herdr 交互 skill，要求实际 ID、指定目标、无焦点创建和结果回读。
- 新回归用例在修复前失败；修复后配置测试 9 项通过。
- 全套实际执行：`/Users/nocoo/.hermes/hermes-agent/venv/bin/python -I -B tests/run.py`，**86 项通过，14.183 秒，退出码 0**。这是离线 fixture 测试；原 84 项历史完整输出仍保存在 [12](12-离线实现与验证.md)。

## 13.4 下一次切换：必须先获停服确认

1. 重新确认 cherry 身份、无进行中的请求，以及配置/备份 hash。只读展示实际差异和当前进程。
2. 获准后 bootout **仅** `ai.hermes.gateway-cherry`，等待已核验的 wrapper/Gateway 退出，再从 LaunchAgents 移除该 plist；保留备份用于回滚。
3. 原实例退出后应用候选配置、SOUL 追加段及 skill。必要时将 cherry 既有运行文件权限改为 0600，保留锁 inode，不删除 Hermes 锁或伪造 PID 状态。
4. `bind --dry-run` → `bind --apply`，确认初始 paused；启用插件，再通过插件 Start 启动。核验真实 pane IDs、进程身份、同 SID，以及两次新鲜平台观察达到 READY。
5. 测试 Discord 消息和 Herdr 交互。任何进一步 Stop/Restart/Pause/Herdr 停服均在获得对应确认后进行。

这次接入切换只停止 cherry。默认 Herdr 的停服会影响其现有 workspace 和任务，需要另一次明确确认；关闭 TUI 界面与停止后台 server 是不同动作，不能混为一个验收结果。

## 13.5 三项目标的验收

| 用户目标 | 验收方式 | 当前结果 |
|---|---|---|
| 随 Herdr 生命周期启停 | 默认 session 冷启动自动产生一个受监管 Gateway；停止 server 后该 Gateway 退出；再次启动重新就绪。记录 PID/start/SID、意图、pane IDs 和实例数 | NOT RUN；待停服确认 |
| cherry 正常工作 | 插件监管下 Discord connected；实际用户消息触发模型并得到带唯一标记的回复 | NOT RUN |
| 读取 Herdr 并双向交互 | Discord 发指令 → cherry 读取真实 snapshot → 在明确的测试 pane 操作 → 回读新的终端结果 → Discord 回报；用独立核查比对实际输出 | NOT RUN |

重复 ensure 不新增进程、暂停不复活、restart 保持 supervisor 等离线断言仍需在真实运行中补证。当前不能承诺自动孤儿回收；UNKNOWN/ORPHAN 必须阻止替代启动并保留证据。

## 13.6 回滚顺序

获得需要的停服确认后，先持久 Pause，并核验插件 Gateway/已确认后代确已退出，再 disable 插件。恢复本次修改的 config/SOUL；新增 skill 只有 hash 仍匹配本次安装时才移除。恢复原 plist 并 bootstrap 原 LaunchAgent，重新检查原 cherry 的身份、Discord 连接和消息回复。

如果进程归属或退出结果不明，保持暂停并核验现场，不并行拉起旧 LaunchAgent。保留 Profile 历史、会话及凭据；私有备份和运行数据不提交 Git。
