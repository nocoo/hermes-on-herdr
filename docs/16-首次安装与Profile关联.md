# 16 · 首次安装与 Profile 关联

**状态：设计方案，0.1.1 尚未实现关联向导。** 已实现的是读取私有配置后的 `bind`，手动步骤见[发布与安装](15-发布与安装.md)。这里定义普通新用户的下一步流程。

## 用户流程

用户在 Hermes 中自行配置模型、凭据和消息平台，再选择一个已有 Profile，让它的 Gateway 随当前 Herdr session 运行。插件保存该 Profile 与 Herdr 的关联，不另建名叫 herdr 的 Profile，也不把 `cherry` 改名。

```mermaid
flowchart LR
    A[在 Herdr 安装插件] --> B[选择已有 Profile]
    B --> C[自动检查可用性]
    C --> D[关联并启动]
    D --> E[Gateway 启动状态页]
    E -->|用户按 Enter| F[完整监控面板]
    C -->|已有外部 Gateway| G[展示接管步骤，停服前确认]
```

正常路径只要求选择 Profile 并点击“关联并启动”。只有一个符合条件的命名 Profile 时可预选，但不自动接管。1–2 个直接列出，更多时使用可滚动、可搜索的列表。默认 Profile 仍可被监控，首版托管范围保持为命名 Profile。

选择页显示名称、Gateway 是否运行、能否关联及具体原因。选中项可显示模型和平台摘要；解释器路径、socket 和内部 ID 放入可展开的诊断信息，用户不必手填这些字段。

## 自动定位与关联

| 信息 | 获取方式 |
| --- | --- |
| 当前 Herdr | 从真实插件 pane/hook 的 owner 环境获得，不猜测 default socket |
| 插件代码、配置目录 | Herdr 注入的目录或原生查询命令，支持自定义 XDG 位置 |
| Hermes 与解释器 | 检查本机 Hermes 入口及其 venv，保留 venv 解释器路径 |
| Profile 列表 | 按 Hermes 数据目录规则发现命名 Profile，仅枚举元数据 |
| 工作目录 | 沿用所选 Profile 的 terminal 配置，不改成插件 checkout |
| 期望平台 | 选中后从配置识别；有歧义时显示候选供确认 |

macOS、Linux 共用这套流程。多个 Hermes 安装、解释器缺失或自定义数据目录时，再显示一次路径选择。发现阶段不启动 Hermes agent，不扫描所有 Profile 的凭据。

建议先增加配置前可用的 `setup` 入口，用同一段逻辑支持 TUI 和脚本。拟新增命令如下，**当前不可执行**：

```text
hermes-on-herdr setup
hermes-on-herdr setup --profile cherry
hermes-on-herdr setup --profile cherry --start
```

`setup` 进入选择流程，指定 `--profile` 跳过选择。关联保存配置并复用 `bind --apply`，初始暂停；`--start` 或 TUI 的“关联并启动”按钮才明确允许运行。TUI 另提供“仅关联，稍后启动”。首次启动缺少配置时进入关联页，不再只显示 `SETUP_REQUIRED` JSON。

关联完成后进入现有 Gateway 状态页。完整监控仍默认关闭，保留“以后自动打开监控”的未勾选复选框。

## 配置差异与已有 Gateway

现有 `profile_preflight` 检查 terminal backend、工作目录、自动加载 shell 配置、插件、工具集和 multiplex 等设置，大多数失败统一返回 `CONFIG_ERROR`。因此自动填 JSON 还不足以让一般用户顺利接入。

向导需把检查转成逐项、可行动的结果，例如“当前 terminal backend 为 docker，关联 Herdr 需要 local”。保留用户的模型、凭据和平台。不能因为选择关联，就把普通 Profile 改成示例限制模板；需要调整的项目应列出原因和具体差异，交给用户处理。首轮优先支持已满足条件的专用 Profile 一次完成关联。

| 检查结果 | 交互与行为 |
| --- | --- |
| Profile 已就绪，Gateway 未运行 | 允许关联；“关联并启动”在真实 pane 中启动 Gateway |
| 已绑定同一 Profile、同一 owner | 显示当前关联，不重复初始化、不重置暂停或熔断 |
| Gateway 正由原生命令、launchd 或 systemd 管理 | 显示“等待接管”和启动方式；先确认停服，再处理该 Profile 的原生管理，核验退出后才能启动插件实例 |
| 已由另一个 Herdr session 管理 | 显示所属 session 和冲突，不迁移所有权 |
| 配置不兼容或路径无权限 | 显示具体项和修复入口，保留所选 Profile |
| Hermes 未安装、版本不兼容或没有命名 Profile | 展示准备步骤，完成后可重新检查 |

切换已有托管 Profile 属于明确的管理动作，不混在安装脚本里。接管流程不能根据进程名批量终止 Gateway，也不能删除所有 Hermes 的系统服务配置。

## 实现顺序与验收

先实现自动定位、所选 Profile 的结构化检查、幂等写入插件配置并绑定。复用路径校验、`bind`、持久意图和 controller，保持 Hermes 的配置与凭据原样。再把同一逻辑接入 hqtui 首次启动页，无需引入新的安装框架。

测试应证明：

- macOS、Linux 路径与 venv 符号链接定位正确；多个安装时不静默选错。
- 只关联指定 Profile，其他 Profile 的运行状态不变；所选及其他 Profile 的 Hermes 文件均保持字节一致。
- 取消、写入失败或预检失败不留下允许自动启动的半成品；重试和并发 setup 不重复创建绑定。
- 重复关联保留暂停与熔断；遇到其他 owner 或外部 Gateway 时不自动停服、不启动第二个实例。
- 未配置的首次启动能操作选择页；列表、键盘、鼠标、窄窗口及取消路径有真实 PTY 测试。
- 成功以身份和期望平台 READY 为准，失败显示具体原因；完整监控默认不自动打开。

真实验收沿用隔离 Profile。涉及停止当前 Gateway 时另行确认，离线测试通过后再验证安装、选择、关联、冷启动和退出清理的完整路径。
