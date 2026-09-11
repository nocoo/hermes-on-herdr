# 14 · hqtui 监控面板

记录日期：2026-09-12。面板已实现并完成离线验证；本轮没有停止或重启 Herdr、cherry，也没有将新面板接入正在运行的实例。

## 14.1 界面与布局

新的 supervisor 在真实 TTY 中自动打开 `HERMES CONTROL`，使用 [hqtui](https://github.com/profullstack/hqtui) 的 Python 实现。依赖固定到 `d9a841494bab910403737a8c791d6d96ef52e878`，以未修改的源码随仓库提供；无需安装 Node 或从 PyPI 下载同名包。[来源、MIT 许可与文件摘要](../vendor/README.md)。

![双 profile 面板，离线演示数据](evidence/dashboard-two.png)

- 1 个 profile：主卡片、主机概况和状态事件。
- 2 个 profile：上下两张卡片，右侧分别为主机概况和事件；列宽对齐。
- 更多 profile：顶部固定 Herdr 专属卡片，下方为可滚动列表及选中项详情。卡片模式按选中项分页。
- 窄窗口：保留专属 profile 摘要、列表、主机一行概况和常用快捷键。
- Herdr 管理的 profile 始终以金色边框、`HERDR MANAGED` 和 `PINNED` 标识；选择或过滤其他 profile 时仍保留。

其他尺寸预览：[单 profile](evidence/dashboard-one.png)、[20 个 profile](evidence/dashboard-fleet.png)、[80×24 窄窗口](evidence/dashboard-narrow.png)。这些图片由真实 hqtui framebuffer 导出，右上角标有 `DEMO`，内容全部为合成数据。

## 14.2 监控范围与数据含义

从插件已绑定 profile 推导 Hermes 根目录，发现同一用户的 `default` 和 `profiles/*`。例如绑定 `~/.hermes/profiles/cherry` 时，覆盖该 `~/.hermes` 下的全部标准 profile。发现过程跳过符号链接、删除标记和不安全目录。独立放在其他 `HERMES_HOME` 根目录中的 profile 需要另行接入，当前不会遍历磁盘寻找它们。

每个 profile 展示 Gateway 状态、PID、运行时间、平台连接、活动 Agent 数、进程 CPU、RSS 和最近观察时间。活动数仅在原生接口提供有效值时显示。

| 标记 | 含义 |
| --- | --- |
| `READY` | 专属 profile 的原生实时状态与 Herdr 所有权检查均通过 |
| `RUNNING` | 外部 profile 的原生接口确认正在运行 |
| `DEGRADED` | 平台连接异常或需要处理 |
| `SHARED` | 由另一个 Gateway 复用服务；显示来源，不重复计算资源和平台连接 |
| `STOPPED` | 没有可确认存活的 Gateway；单凭一个过期 PID 文件不会报告运行 |
| `SCANNING` | 尚未轮询到的 profile |
| `UNKNOWN` / `STALE` | 无法验证或观测过期；隐藏当前连接、CPU、RSS 和活动数，保留明确的状态提示 |

CPU 的 `100%` 表示占满一个逻辑核；RSS 只计算 Gateway 本进程。历史图按最近 90 个观测样本绘制，采样间隔可变。RSS 图使用标出的局部纵轴。事件区保留最近 24 条**观察到的状态变化**，不读取聊天内容或原始日志。

采样不会读取 profile 的 `config.yaml`、`.env`、会话或数据库；原生 socket 只使用 `identify`、`status`。其他 profile 的生命周期仍由各自的启动方式管理。

## 14.3 开销控制

| 项目 | 策略 |
| --- | --- |
| 默认采样 | 2 秒，可调整为 5 或 10 秒 |
| 优先级 | Herdr 专属 profile、当前选中项优先，其余轮询 |
| 每轮工作量 | 最多探测 4 个 profile；每个原生请求上限 150 ms，专属 owner 检查预算 500 ms |
| 目录发现 | 每 30 秒刷新一次 |
| 主机指标 | 仅非阻塞 CPU 利用率与内存概况，可关闭；不扫描全机进程表 |
| 失焦 | 终端支持并发送 focus 事件时，降为 10 秒采样并暂停自动绘制 |
| 隐藏 | `q` 隐藏后按 10 秒采样，并关闭主机指标采样 |
| 渲染 | 数据或交互变化时重绘；只输出变化的字符单元；不订阅无按键的鼠标移动 |
| 并发 | 一个采样线程；嵌入模式另有一个阻塞等待父进程生命周期的线程 |

1–2 个 profile 每轮都能覆盖。大量 profile 的首次完整状态采样和后台刷新会分散到多个周期；选中任意 profile 后，它在下一轮获得优先采样。界面显示观测年龄，过期数据不会继续以健康状态展示。

## 14.4 交互

| 操作 | 效果 |
| --- | --- |
| `j/k`、方向键 | 选择 profile |
| `PgUp/PgDn`、`Home/End` | 大步移动，或跳到首尾 |
| 鼠标点击、滚轮 | 选择和滚动列表 |
| `/`、输入名称、`Enter` | 按名称过滤；`Esc` 清除过滤 |
| `l` | 切换自动、卡片、列表布局 |
| `t` | 切换 Herdr、Nord、高对比度、单色主题 |
| `s` | 开关主机指标 |
| `+/-` | 在 2、5、10 秒之间加快／减慢采样 |
| `?` / `F1` | 帮助 |
| 嵌入面板中的 `q` | 隐藏／恢复面板，Gateway 继续运行 |
| 嵌入面板中的 `Ctrl+C` | 沿用原有 supervisor 契约，持久暂停专属 Gateway |
| 独立监控窗口中的 `q` / `Ctrl+C` | 关闭该监控窗口 |

布局、主题、主机指标开关和采样间隔保存在插件配置目录的 `dashboard.json`，权限 `0600`，原子替换。过滤内容和选择项不持久化。损坏的偏好回退为默认值；符号链接、共享文件或其他不安全目标不会被覆盖。

## 14.5 生命周期隔离

面板与 Gateway 是 supervisor 的两个独立子进程。Gateway 输出继续由原有日志路径消费，渲染不会进入 Gateway 的输出管道。面板只继承终端显示所需的少量环境变量。

嵌入面板通过专用 socketpair 把 `Ctrl+C` 交给自己的 supervisor，随后由原有持久暂停逻辑处理。它不会搜索父 PID 并发送信号。面板启动失败、异常退出或输出阻塞时，Gateway 的监督与控制仍然可用。父进程退出会关闭生命周期通道，面板即使卡在绘制或采样中也会退出；终端模式恢复使用非阻塞输出。

`TERM=dumb`、非 TTY 或 supervisor 环境设置 `HGH_DASHBOARD=0` 时不自动启动面板。独立 `dashboard` 命令在输出被重定向时只打印一帧，不持续写 ANSI 控制流。

## 14.6 测试与测量

完整离线回归 **135 项通过**，[完整输出](evidence/dashboard-unittest.txt)。最终窄窗口布局调整后，12 项渲染测试也全部通过。

新增测试覆盖身份伪造和 PID 复用、慢 socket、轮询公平性和上限、共享 Gateway 计数、CPU 时间差及历史长度、1/2/25 个 profile 的多尺寸布局、过滤和滚动定位、偏好文件安全、真实 PTY 输入与 resize、失焦降频、高频按键不加快采样，以及面板退出／崩溃／阻塞对 Gateway 生命周期的隔离。配置和状态文件的 FIFO 回归使用真实 launcher 验证。

```sh
/absolute/path/to/hermes/venv/bin/python -I -B tests/run.py
```

2026-09-12 在 macOS arm64、Python 3.11.15、160×44 终端上测量完整的嵌入面板进程。各阶段测量 20 秒，预热后计数。CPU 包含渲染、采样、原生 RPC 和进程指标读取；内存是该面板进程 RSS。原有 supervisor、被监控服务和测试工具的资源未计入。对端全部使用临时目录与本地假 Gateway：一个由真实 supervisor 代码管理，其余 profile 的协议响应由测试进程提供。

| profile 数 | 状态 | CPU，单核口径 | RSS 中位数 | 终端输出 |
| --- | --- | --- | --- | --- |
| 2 | 前台 | 0.482% | 35.34 MiB | 371 B/s |
| 2 | 隐藏 | 0.053% | 35.41 MiB | 0 B/s |
| 50 | 前台 | 0.635% | 35.20 MiB | 663 B/s |
| 50 | 隐藏 | 0.059% | 35.23 MiB | 2 B/s |

同尺寸、90 个历史样本的纯渲染测量：1/2/50/1000 条 profile 的中位数分别为 5.30/6.30/7.91/9.53 ms。1000 条的 P95 为 9.90 ms；这一项只测 hqtui framebuffer 绘制。原始数字和测量范围见 [JSON 记录](evidence/dashboard-benchmark.json)。

```sh
/absolute/path/to/hermes/venv/bin/python -I -B tools/dashboard_benchmark.py \
  --profiles 2 50 --seconds 20 --output /tmp/dashboard-benchmark.json
```

## 14.7 查看与启用

不连接真实服务的 HTML 预览：

```sh
/absolute/path/to/hermes/venv/bin/python -I -B tools/dashboard_preview.py \
  --profiles 2 --width 160 --height 44 --output /tmp/hermes-control.html
```

已有有效插件配置时，可以独立运行演示 TUI；此模式不会构造真实采样器：

```sh
./bin/hermes-gateway-herdr --config /absolute/config.json dashboard --demo-profiles 2
./bin/hermes-gateway-herdr --config /absolute/config.json dashboard --demo-profiles 20
```

真实只读监控入口，以及一次性文本／JSON 快照入口：

```sh
./bin/hermes-gateway-herdr --config /absolute/config.json dashboard
./bin/hermes-gateway-herdr --config /absolute/config.json dashboard --snapshot
./bin/hermes-gateway-herdr --config /absolute/config.json dashboard --json
```

自动嵌入在**新的 supervisor 启动时**生效。现有 supervisor 已加载旧代码；只重启 Gateway child 不会加载新面板。本机插件仍链接到这个仓库，下一步可在用户确认后，通过既有 Pause/Resume 或 Herdr 生命周期重新创建 supervisor，再检查真实颜色、字体、focus 事件和 profile 状态。本轮保留当前运行实例，真实验证和停服继续遵守“先确认”的要求。

返回 [文档索引](README.md) · [cherry 接入记录](13-cherry接入与验证.md)。
