<h1 align="center">Hermes Gateway for Herdr</h1>
<p align="center">在真实 Herdr pane 内监督专用 Hermes Gateway，保留明确的运行意图与进程所有权。</p>
<p align="center"><a href="docs/README.en.md">English</a></p>

让 Herdr 启动后自动确保一个专用 Hermes Gateway 运行在真实 Herdr pane 内，继承 `HERDR_SOCKET_PATH`、`HERDR_WORKSPACE_ID`、`HERDR_TAB_ID`、`HERDR_PANE_ID`，成为面向该 Herdr session 的控制 Agent。

**当前状态：首轮离线核心已实现，84 项测试通过，真实环境验证待确认。** 已有 controller、pane supervisor、开发用 manifest、隔离 launcher 和命令入口。目前未安装插件、未创建或修改用户 Hermes Profile、未启动真实 Gateway。实现范围、原子提交和测试证据见 [12 · 离线实现与验证](docs/12-离线实现与验证.md)。

离线测试使用已配置 Hermes venv 中的 Python 3.11+、psutil 和 PyYAML，不导入 Hermes main，不调用已安装的 Herdr／Hermes：

```sh
/absolute/path/to/hermes/venv/bin/python -I -B tests/run.py
```

测试使用临时目录、假 Herdr RPC 和受控 Python 假 Gateway，覆盖并发创建、响应丢失、进程退出、暂停竞态、PID 复用、后台任务清理和日志背压。[完整输出](docs/evidence/offline-unittest.txt)记录了 macOS 上的实际结果；Linux、真实 PTY/handoff 和消息往返均未验证。

`status`、`doctor`、`logs` 提供 JSON 诊断；`bind` 默认只展示既有专用 Profile 的绑定计划；Start/Resume 才持久允许运行。新 Profile 初始化器、孤儿自动回收、维护/升级工具和系统服务仍未实现。识别到孤儿或未知启动结果时会阻止替代实例；`stop --wait` 不会把这种状态报告为已停止。

## 使用与开发

当前交付是离线实现和开发用 manifest。先阅读 [配置示例](examples/README.md) 与 [真实环境验证清单](docs/05-实现步骤.md)，再准备独立的测试 session、专用 Profile 和配置；没有一键安装或自动创建 Profile 的流程。

查看 launcher 帮助无需配置，也不会连接 Herdr 或 Hermes：

```sh
./bin/hermes-gateway-herdr --help
```

运行时使用 Python 3.11+，复用已配置的 Hermes venv；依赖见 [requirements.txt](requirements.txt)。入口用系统 Python 检查私有解释器提示文件，再以隔离模式启动配置中的 venv Python。配置目录需为 `0700`，`config.json` 与 `runtime-python` 需为 `0600`；后者的一行绝对路径必须与 `python_bin` 一致。

完成独立配置后，以下命令可读取状态或查看绑定计划。路径为占位符，需要替换为已审阅的配置：

```sh
./bin/hermes-gateway-herdr --config /absolute/config.json status --json
./bin/hermes-gateway-herdr --config /absolute/config.json doctor --json
./bin/hermes-gateway-herdr --config /absolute/config.json bind --dry-run
```

| 命令 | 行为 |
| --- | --- |
| `bind` / `bind --dry-run` | 展示既有专用 Profile 的控制目录计划 |
| `bind --apply` | 初始化控制目录，初始暂停；不创建 Profile 或启动 Gateway |
| `start` / `resume` | 明确允许运行，再执行 ensure；收到 ACK 不代表就绪 |
| `pause` / `stop` | 先持久记录暂停，再通知 supervisor |
| `stop --wait 30` | 最多等待 30 秒，核验完成后才报告已停止 |
| `restart` | 仅对允许运行的实例请求重启，不隐式恢复暂停 |
| `status --require-ready` | 仅已确认 READY 返回成功；不证明模型或 bot 消息往返可用 |
| `logs --lines 50` | 读取结构化生命周期事件，不导出原始 child 输出 |

Herdr hooks 使用 `ensure`，真实 pane 使用 `supervise`。从 hook 外手动执行控制动作时，使用全局 `--owner-socket /absolute/bound.sock` 指明绑定的 owner。完整参数、返回码与重试契约见 [离线实现与验证](docs/12-离线实现与验证.md#124-当前命令契约)。

## 技术栈

| 技术 | 用途 |
| --- | --- |
| Python / 标准库 unittest | Controller、supervisor、CLI 与离线故障测试 |
| Unix sockets / JSONL | 有时限的 Herdr 与 Hermes 控制协议 |
| flock / 原子 JSON 文件 | 单例锁、持久意图、revision 与请求去重 |
| psutil | 进程身份和已确认的后代进程检查 |
| PyYAML | 专用 Hermes Profile 的配置预检 |
| Herdr plugin TOML | 开发用 startup、events、actions 与 pane 注册 |

## 结论

**有约束可行（feasible with constraints）**。推荐所有权链：

```mermaid
flowchart LR
    OS["launchd / systemd<br/>可选：监管 Herdr"] --> H["Herdr Server"]
    H --> C["Herdr plugin hooks<br/>幂等 ensure"]
    C --> P["专用 workspace / tab / pane"]
    P --> S["pane 内 supervisor"]
    S --> G["专用 Profile 的 Hermes Gateway<br/>foreground + external-supervisor"]
    G -->|"真实 HERDR_* / CLI / socket"| H
```

- Herdr v0.9.0 支持 argv plugin pane 和真实环境注入；startup hook 仅是异步启动命令，不承担进程监督。[H03–H04](docs/09-源码证据索引.md#h03)
- 同一机器、同一 OS 用户的专用 Profile `herdr-control` 只绑定一个配置指定的 Herdr session；其他 session 的 hook 不争抢它。需要多个 Gateway 时必须分别配置 Profile、平台 token 和所有权。[架构决策](docs/08-决策记录.md)
- Hermes 指定版本已有 `gateway.sock`。身份响应、实时 status 和期望平台 connected 可组成最小 readiness probe；它仍不证明模型调用和消息端到端可用。[M10–M11](docs/09-源码证据索引.md#m10)
- 冷恢复不重放保存的普通 launch argv；live handoff 可以保留 PTY/process，但丢失 Herdr 内存中的 plugin ownership，且重跑 startup hooks。必须用锁、活身份和本插件账本去重，不能只按 pane label 判断。[H07–H09](docs/09-源码证据索引.md#h07)
- Stop/Pause 持久记录暂停，显式 Start/Resume 才清除；75 重启、1 重试、0 停止、2/78 熔断都要结合已持久化的意图判断。[生命周期](docs/03-生命周期设计.md)
- Herdr 崩溃时接受 Gateway 中断，Herdr 恢复后重建。handoff 后 supervisor 本身失效可能没有退出事件；无人值守、有恢复时限的模式还需要周期性短 ensure。原生服务管理下的 live handoff 在 spike 通过前不支持。[限制](docs/01-可行性分析.md)

Profile 是状态隔离，不是 sandbox。持有真实 Herdr socket 并能执行本地 terminal 命令的 Agent 具有同 UID 的广泛能力，persona 不能把它变成资源级硬隔离。[安全边界](docs/07-安全与运维.md)

## 文档

| 文档 | 内容 |
|---|---|
| [文档索引](docs/README.md) | 阅读顺序、证据等级和术语 |
| [01 · 可行性分析](docs/01-可行性分析.md) | 源码复核、prior art、替代方案、风险 |
| [02 · 系统架构](docs/02-系统架构.md) | 组件、所有权、协议、schema、状态机 |
| [03 · 生命周期设计](docs/03-生命周期设计.md) | ensure、恢复、重启、暂停、卸载算法 |
| [04 · Hermes 专用 Profile 设计](docs/04-Hermes专用Profile设计.md) | 初始化、配置、persona、skills、凭据 |
| [05 · 实现步骤](docs/05-实现步骤.md) | 先 spike，再按阶段实现和验收 |
| [06 · 测试与验证](docs/06-测试与验证.md) | 单元／集成／E2E／故障注入矩阵 |
| [07 · 安全与运维](docs/07-安全与运维.md) | 权限、日志、故障排查、OS 服务、升级 |
| [08 · 决策记录](docs/08-决策记录.md) | ADR 及推翻条件 |
| [09 · 源码证据索引](docs/09-源码证据索引.md) | commit、path、symbol、官方文档、GitHub 查询 |
| [10 · 实施任务清单](docs/10-实施任务清单.md) | P0/P1/P2、依赖和 DoD |
| [11 · 研究与验证记录](docs/11-研究与验证记录.md) | 实际执行的研究与文档检查、未执行项 |
| [12 · 离线实现与验证](docs/12-离线实现与验证.md) | 已实现命令、测试证据、已知限制与下一步门禁 |

## 固定基线

| 组件 | 版本 | 源码提交 |
|---|---|---|
| Herdr | 本机及 tag：v0.9.0 | [`b99002ac99b09e00b4ca692436cb15a6b0d676f1`](https://github.com/herdrdev/herdr/tree/b99002ac99b09e00b4ca692436cb15a6b0d676f1) |
| Hermes Agent | 本机：v0.21.1 (2026.9.7) | [`b7ac3ba1cdf89f94dfe86de27e01358b194f4053`](https://github.com/NousResearch/hermes-agent/tree/b7ac3ba1cdf89f94dfe86de27e01358b194f4053) |
| 官方文档 | 2026-09-11 在线抓取 | 非版本化；与源码不一致时明确列出差异 |

同类实现的六个本地 reference 和新发现候选也固定到 SHA，详见 [证据索引](docs/09-源码证据索引.md)。研究未发现满足全部目标的公开 exact plugin；搜索范围与限制已记录，不能据此证明不存在。

## 范围与非目标

目标宿主是 **Herdr plugin**：`herdr-plugin.toml` 注册外部命令、hooks、actions、panes。Hermes Python plugin 使用 `plugin.yaml` 并加载进 Hermes 进程；后续可作为受审计的辅助能力，本架构不依赖新增 Hermes plugin 管理生命周期。

首版面向 host macOS/Linux、单用户、单机、明确绑定的一个 session。Windows、跨机器 HA、热迁移 bot token、Herdr 不在时 Gateway 继续服务、对任意恶意本地代码的强隔离都不在首版范围。本阶段也不改变现有 Hermes integration、其他 Profile、系统服务或 reference 仓库。

仓库名 `hermes-gateway-herdr` 符合已观察到的 `<thing>-herdr` 命名惯例；拟定 manifest ID 为 `nocoo.hermes-gateway`，entrypoint 为 `gateway`，两者不要求与 repo 名相同。

下一步经确认后执行 [P0 spike](docs/05-实现步骤.md)。开发用 manifest 的存在不代表真实集成或发布门禁已经通过；配置示例只供审阅，见 [examples](examples/README.md)。
