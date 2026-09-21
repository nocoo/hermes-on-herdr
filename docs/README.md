# hermes on herdr 文档

[中文首页](../README.md) · [English overview](README.en.md) · [配置示例](../examples/README.md)

hermes on herdr 通过 Herdr plugin，把用户显式选择的专用 trusted Hermes Profile 链接到当前 Herdr session，补齐外部独立 Hermes 不会天然拥有的受管 pane、socket 与 caller context。专用 Hermes 获得该 session 的完整 Herdr 控制权限，作为 M2 管理 Herdr；人与 M2 之间复用 Hermes 已有的 Discord、Telegram、Slack 等 channels，日常远程管理无需先 SSH、接管桌面或为 Herdr 配置 VPN、暴露控制端口。

绑定仍受 Herdr 的本地访问权限和插件的归属、生命周期规则约束，不是同 UID 资源隔离。首屏定位与边界说明见 [中文首页](../README.md#架构与信任边界) / [English overview](README.en.md#architecture-and-trust-boundaries)。这套文档分别记录当前使用方法、实现契约、设计提案与历史验证；消息平台和端到端能力以本页的验证范围为准。

## 从这里开始

| 目的 | 阅读路径 |
| --- | --- |
| 理解控制上下文缺口、M2 与消息渠道 | [为什么需要插件](../README.md#这是什么) → [架构与信任边界](../README.md#架构与信任边界) |
| 安装、升级、发版与版本约定 | [发布与安装](15-发布与安装.md) → [首次关联方案](16-首次安装与Profile关联.md) |
| 准备配置、接入专用 Profile | [配置示例](../examples/README.md) → [实现及验收计划](05-实现步骤.md) → [cherry 接入记录](13-cherry接入与验证.md) |
| 使用常驻 dashboard 和 Gateway 启停按钮 | [监控面板](14-hqtui监控面板.md) |
| 查看状态、排查问题 | [命令契约](12-离线实现与验证.md#124-当前命令契约) → [安全与运维](07-安全与运维.md) |
| 修改核心实现 | [系统架构](02-系统架构.md) → [生命周期](03-生命周期设计.md) → [测试与验证](06-测试与验证.md) → [质量评估](17-插件质量评估.md) |
| 理解设计依据与剩余工作 | [决策记录](08-决策记录.md) → [源码证据](09-源码证据索引.md) → [任务清单](10-实施任务清单.md) |

## 当前验证范围

Version 0.1.5 retains the Controller, supervisor, CLI, persistent Dashboard, recovery UI and read-only HTTP monitor. It removes Hermes source pins and Profile configuration policy checks; see the [compatibility contract](18-Herdr兼容策略.md). The [local regression record](evidence/release-0.1.5-unittest.txt) covers Python 3.11 and 3.14; [CI](../.github/workflows/tests.yml) also covers Ubuntu and macOS. The 0.1.1 [coverage assessment](17-插件质量评估.md) is historical and has not been remeasured. The first-run Profile wizard remains a design proposal.

常驻 Dashboard 提供 Gateway 启停按钮、配置受阻重试和 renderer 自动恢复；独立恢复中心提供无参数命令、原生 popup 和持久标签提示。行为及恢复矩阵见 [监控面板](14-hqtui监控面板.md)；[恢复验证](evidence/recovery-validation.txt)记录隔离原生检查、本机运行观察和此前未定位根因的偶发 FIFO CLI 超时。

`v0.1.0` 的历史运行快照曾核验 cherry 官方安装、READY、唯一 Gateway 的 Herdr/plugin 归属、Discord 连接、嵌入终端监控及 HTTP 健康 200，证据见 [13.7](13-cherry接入与验证.md#137-正式-010-发布安装与运行验收)。Telegram、Slack 是 Hermes 上游已有渠道，当前尚无本插件对应的真实接入验收记录。新消息/模型往返、完整冷启动、退出清理、指定 pane 双向交互、Linux 真实接入和 Herdr 在线升级 handoff 仍待验证。[12](12-离线实现与验证.md) 的 84 项、[13](13-cherry接入与验证.md) 的 90 项及用户消息反馈，以及面板早期批次是各阶段的历史证据。

0.1.1 的[升级及现场观察](13-cherry接入与验证.md#138-011-升级与运行观察)记录了正式安装、一次 UNKNOWN 退出及恢复后的 READY / Discord / HTTP 200。90 秒观察未再报错；退出根因仍未定位，短时观察不能证明长期稳定。

设计文档中的新 Profile 初始化器、系统服务、自动孤儿回收与升级工具属于后续计划。实际可用参数以 CLI 和 [当前命令契约](12-离线实现与验证.md#124-当前命令契约) 为准。

## 完整索引

| 编号 | 文档 | 内容 |
| --- | --- | --- |
| 01 | [可行性分析](01-可行性分析.md) | 早期研究、约束与替代方案 |
| 02 | [系统架构](02-系统架构.md) | 组件、身份、锁、状态与协议 |
| 03 | [生命周期设计](03-生命周期设计.md) | 并发、异常、恢复与暂停语义 |
| 04 | [Hermes 专用 Profile 设计](04-Hermes专用Profile设计.md) | Profile、权限、凭据和运行环境 |
| 05 | [实现步骤](05-实现步骤.md) | 接入 spike、实现阶段和验收门槛 |
| 06 | [测试与验证](06-测试与验证.md) | 复现方法、断言和故障注入矩阵 |
| 07 | [安全与运维](07-安全与运维.md) | 诊断、权限、升级与服务设计 |
| 08 | [决策记录](08-决策记录.md) | ADR、理由与重新决策条件 |
| 09 | [源码证据索引](09-源码证据索引.md) | 固定提交、源码符号与官方文档 |
| 10 | [实施任务清单](10-实施任务清单.md) | 优先级、依赖与完成定义 |
| 11 | [研究与验证记录](11-研究与验证记录.md) | 研究阶段执行过的检查及其边界 |
| 12 | [离线实现与验证](12-离线实现与验证.md) | 当前命令契约与首轮核心测试记录 |
| 13 | [cherry 接入与验证](13-cherry接入与验证.md) | 真实接入、READY、消息验证与待办 |
| 14 | [hqtui 监控面板](14-hqtui监控面板.md) | 常驻恢复、启停按钮、布局、采样、PTY 测试与测量 |
| 15 | [发布与安装](15-发布与安装.md) | GitHub 分发、原生安装、SemVer、升级回滚和 Linux 兼容 |
| 16 | [首次安装与 Profile 关联](16-首次安装与Profile关联.md) | 已有 Profile 的关联向导设计、配置差异和接管流程 |
| 17 | [插件质量评估](17-插件质量评估.md) | ponytail 评估、异常输入回归、覆盖率与复现命令 |
| 18 | [Herdr and Hermes compatibility](18-Herdr兼容策略.md) | Required APIs, launch ownership and native Herdr evidence |

## 命名约定

| 用途 | 名称 |
| --- | --- |
| 对外品牌 | `hermes on herdr` |
| GitHub 仓库 | [`nocoo/hermes-on-herdr`](https://github.com/nocoo/hermes-on-herdr) |
| 命令入口 | `bin/hermes-on-herdr` |
| 已安装插件 ID / pane entrypoint | `nocoo.hermes-gateway` / `gateway` |
| Python 包 | `hermes_gateway_herdr` |

项目于 2026-09-12 从 `hermes-gateway-herdr` 改名。现有安装、所有权记录和 Python 导入使用上述内部标识；旧 launcher 是当前命令的兼容链接。旧名称在原始设计档案、源码搜索记录和本机私有备份路径中保留，便于追溯。新文档和操作示例使用新品牌与命令名。Logo 来源见 [品牌说明](../assets/brand/README.md)。

## 证据等级

| 标记 | 含义 |
| --- | --- |
| V | 实际观察或执行；仅证明注明范围的检查，用户反馈另行标明 |
| S | 固定 SHA 的源码；不等于真实环境集成测试 |
| D | 抓取时的官方文档；可能领先于本机代码 |
| A | 类似实现，供设计参考 |
| P | 本项目设计提案，需核对实现状态 |
| X | 待 spike 验证的假设 |

Hxx/Mxx 指向源码证据，Pxx 指向类似实现，Oxx 指向官方文档。标注“拟定”“要求”“默认值”的设计条目不代表上游已提供该功能；未记录执行结果的命令不算验证证据。源码与在线文档冲突时，保留差异并以目标 SHA 为准。

## 术语

| 术语 | 含义 |
| --- | --- |
| Herdr session | 一个 Herdr Server/API socket 管理的 workspace 集合 |
| owner session | 配置中唯一允许拥有该专用 Gateway 的 Herdr session |
| Profile | Hermes 的 HERMES_HOME 命名空间，不提供容器隔离 |
| controller | hook、action 或 timer 调用的一次性短进程 |
| supervisor | pane 内持有 lifetime lock、监督一个 Gateway child 的前台进程 |
| adopt / replace | 接受已核验的存活实例并修复账本 / 安全回收后创建替代实例 |
| READY | 活身份、运行状态和期望平台满足有限就绪条件 |
| pause / fuse | 持久禁止 Gateway 自动启动 / child 致命退出或重试超限后熔断；dashboard 保留 |

启动要求已有且配置完成的专用 Profile；终止和清理限定到已验证的进程身份。真实环境启停的授权与验收要求记录在 [cherry 接入](13-cherry接入与验证.md)。
