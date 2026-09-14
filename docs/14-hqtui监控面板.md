# 14 · hqtui 监控面板

更新日期：2026-09-14。0.1.2 改为常驻 dashboard，并加入独立恢复入口。正式 0.1.0 的历史终端监控与网页实测见 [13.7](13-cherry接入与验证.md#137-正式-010-发布安装与运行验收)。

## 14.1 界面与布局

版本显示在面板右下角，极窄视图也保留。它与 CLI `--version`、doctor 和插件 manifest 一致，不增加独立页头或额外采样。

品牌为 **hermes on herdr**。插件在自己的 tab 中始终打开完整 dashboard，不再询问是否打开监控。已有 running 意图会自动启动 Gateway；用户显式暂停后，tab 与 dashboard 继续保留，重启 Herdr 也不会清除暂停意图。

专属 Profile 卡片提供 **Start [Enter]** 和 **Pause** 按钮。配置或启动受阻会显示具体检查项，每 30 秒自动重试；点击 Start 可立即重试。崩溃熔断后点击 Start 会重置重试预算。按钮仅控制已绑定的专属 Gateway。

dashboard 使用一个隔离的终端进程和 [hqtui](https://github.com/profullstack/hqtui) 的 Python 实现。依赖固定到 `d9a841494bab910403737a8c791d6d96ef52e878`，以未修改的源码随仓库提供；无需安装 Node 或从 PyPI 下载同名包。[来源、MIT 许可与文件摘要](../vendor/README.md)。

![双 profile 面板，离线演示数据](evidence/dashboard-two.png)

- 1 个 profile：主卡片、主机概况和状态事件。
- 2 个 profile：左侧上下两张卡片，专属卡片占稍多高度；右侧依次为字符图、主机概况和事件。
- 更多 profile：左侧顶部固定 Herdr 专属卡片，下方为可滚动列表；右侧为字符图、主机概况和选中项详情。卡片模式按选中项分页。
- 窄窗口：保留专属 profile 摘要、列表、主机一行概况和常用快捷键。
- Herdr 管理的 profile 始终以金色边框、`HERDR MANAGED` 和 `PINNED` 标识；选择或过滤其他 profile 时仍保留。

其他尺寸预览：[单 profile](evidence/dashboard-one.png)、[20 个 profile](evidence/dashboard-fleet.png)、[80×24 窄窗口](evidence/dashboard-narrow.png)。这些图片由真实 hqtui framebuffer 导出，标有 `DEMO`，内容全部为合成数据。

完整监控不设独立页头。窗口达到 100 列、34 行时，右上 SYSTEM 上方显示用户提供的完整 15 行双蛇杖字符图，保留原有 Unicode 字符和间距。图形只做两秒轻微色彩变化，随后静置十秒；字符形状和位置始终不变。动画表示品牌形象，服务是否健康仍以状态文字为准。窄窗口和帮助页收起图案；失焦时停止动画。`a` 切换静态显示，偏好会被保存。在线数量、LIVE/DEMO 和采样设置位于底栏。

## 14.2 监控范围与数据含义

显示 READY 前执行原生状态与 Herdr 所有权检查；无法确认、连接异常、启动中、暂停、启动受阻或熔断都有明确文字状态。

从插件已绑定 profile 推导 Hermes 根目录，发现同一用户的 `default` 和 `profiles/*`。例如绑定 `~/.hermes/profiles/cherry` 时，覆盖该 `~/.hermes` 下的全部标准 profile。发现过程跳过符号链接、删除标记和不安全目录。独立放在其他 `HERMES_HOME` 根目录中的 profile 需要另行接入，当前不会遍历磁盘寻找它们。

每个 profile 展示 Gateway 状态、PID、运行时间、平台连接、活动 Agent 数、进程 CPU、RSS 和最近观察时间。活动数仅在原生接口提供有效值时显示。

| 标记 | 含义 |
| --- | --- |
| `READY` | 专属 profile 的原生实时状态与 Herdr 所有权检查均通过 |
| `RUNNING` | 外部 profile 的原生接口确认正在运行 |
| `DEGRADED` | 平台连接异常或需要处理 |
| `BLOCKED` | 启动检查或进程创建失败；显示原因，自动重试，也可点击 Start |
| `PAUSED` / `FUSED` | Gateway 保持停止；dashboard 可用，点击 Start 后重新检查并启动 |
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
| 渲染 | 数据、交互或观测年龄变化时重绘监控内容；动画复用一张 hqtui framebuffer，只绘制右侧字符图区域；只输出变化的字符单元 |
| 动画 | 两秒轻微色彩变化、十秒静置；与采样共享一个等待器，使用独立的截止时间，不增加 RPC 或主机指标采样；不订阅无按键的鼠标移动 |
| 并发 | 一个采样线程；嵌入模式另有一个阻塞等待父进程生命周期的线程 |

1–2 个 profile 每轮都能覆盖。大量 profile 的首次完整状态采样和后台刷新会分散到多个周期；选中任意 profile 后，它在下一轮获得优先采样。界面显示观测年龄，过期数据不会继续以健康状态展示。

## 14.4 交互

| 操作 | 效果 |
| --- | --- |
| 嵌入面板中的 Enter / Start | 启动或立即重试专属 Gateway；过滤输入中的 Enter 只确认过滤 |
| 嵌入面板中的 Pause | 持久暂停专属 Gateway，保留 dashboard |
| `j/k`、方向键 | 选择 profile |
| `PgUp/PgDn`、`Home/End` | 大步移动，或跳到首尾 |
| 鼠标点击、滚轮 | 选择和滚动列表 |
| `/`、输入名称、`Enter` | 按名称过滤；`Esc` 清除过滤 |
| `l` | 切换自动、卡片、列表布局 |
| `t` | 切换 Herdr、Nord、高对比度、单色主题 |
| `a` | 开关双蛇杖色彩动画；关闭后保留静态原图 |
| `s` | 开关主机指标 |
| `+/-` | 在 2、5、10 秒之间加快／减慢采样 |
| `?` / `F1` | 帮助 |
| 嵌入面板中的 `q` | 保持 dashboard 打开；在帮助页中返回监控 |
| 嵌入面板中的 `Ctrl+C` | 持久暂停专属 Gateway，保留 dashboard |
| 独立监控窗口中的 `q` / `Ctrl+C` | 关闭该监控窗口 |

布局、主题、主机指标开关、采样间隔和动画开关保存在插件配置目录的 `dashboard.json`，权限 `0600`，原子替换。旧文件的 `auto_open` 被忽略，不影响完整面板打开；其余设置保留，缺少的动画开关默认为开启。过滤内容和选择项不持久化。损坏的偏好回退为默认值；符号链接、共享文件或其他不安全目标不会被覆盖。保存失败会显示提示。

## 14.5 生命周期隔离

面板与 Gateway 是 supervisor 的两个独立子进程。Gateway 输出继续由原有日志路径消费，渲染不会进入 Gateway 的输出管道。面板只继承终端显示所需的少量环境变量。

嵌入面板通过专用 socketpair 把 Start 和 Pause 交给自己的 supervisor，复用持久意图和单实例检查。它不会搜索父 PID 并发送信号。面板启动失败或异常退出后，supervisor 在 5 秒后重开；面板输出阻塞不阻塞 Gateway 的监督与控制。Gateway 暂停或熔断后，supervisor 保留 dashboard，并继续检查 Herdr owner 是否可用。

Herdr 的唯一 startup hook 及 workspace.focused、pane.exited、pane.closed 事件调用同一个 ensure。detach 不结束 pane；live handoff 核验并复用存活 supervisor。冷恢复时在账本记录的专用 workspace 重建 plugin tab，保留 Herdr 恢复出的 shell 和用户工作。无法核验的活进程、未知 spawn 或请求结果仍保留现场，避免重复 Gateway；详见 [生命周期](03-生命周期设计.md)。

supervisor 收到 HUP / TERM 时清理 Gateway 和面板并保留运行意图；下次 startup 在旧进程已结束、账本明确时恢复。Herdr 的强制清理、异常退出和启动竞态仍受下表限制。父进程退出会关闭生命周期通道，面板即使卡在绘制或采样中也会退出；终端模式恢复使用非阻塞输出。`TERM=dumb` 或非 TTY 无法显示交互面板，独立 `dashboard` 在输出被重定向时只打印一帧。

以下为 **2026-09-14 当前实现的恢复矩阵**。基准条件为：插件已启用，重新启动的是同一个绑定的 Herdr session/socket，基础安装与私有账本可读，Gateway 的持久意图为 running，且没有熔断。支持表示存在实现路径；真实重启的验收范围见表后。

| 场景 | dashboard / tab | Gateway | 当前结论与条件 |
| --- | --- | --- | --- |
| TUI 客户端 detach，server 继续运行 | 原 pane 与面板进程保留；客户端关闭期间不可见 | 继续运行 | 支持；detach 只移除客户端连接 |
| TUI 关闭、客户端崩溃或 SSH 断线，server 继续运行 | 原 pane 保留 | 继续运行 | 支持；前提是关闭客户端未同时停止 server |
| 重新 attach 同一个仍在运行的 server | 回到原 tab 即可查看 | 复用原进程 | 支持；attach 本身不重跑插件 startup hook |
| server 停止后重新启动，旧进程已清理 | startup hook 重建 plugin tab | 按 running 意图启动 | 条件支持；旧 tab 可能恢复成 shell 并被保留，新 pane ID 可变化 |
| server 快速重启，startup hook 执行时旧 supervisor 尚在退出 | 首次 ensure 可能返回 UNKNOWN；已保存的 tab / pane 标签保留恢复命令 | 等待旧进程退出 | 不保证自动完成；可运行 hermes-on-herdr，在恢复页重新检查并打开 Dashboard |
| server 崩溃或 SIGKILL 后重启 | 标签保留提示；恢复页不依赖 supervisor，正常归属明确后可重建 | 孤儿进程可能仍在运行，但不会自动接管或复制 | 旧控制器已退出的创建记录可由恢复按钮撤销；ORPHAN、spawn_pending 仍要求确认现场 |
| 电脑重启后，Herdr server 尚未启动 | 外部 shell 可打开恢复页；workspace 要等 Herdr 启动后才可见 | 未启动 | 恢复页可一键打开原 Herdr session，由 Herdr 原生流程启动 server；未提供 OS 自启 service |
| 电脑重启后，同一 Herdr server 已启动 | 按冷启动路径重建 | 正常账本下自动启动 | 条件支持；重启不会清除暂停、熔断或不确定创建记录 |
| Herdr live handoff，PTY 与进程身份延续 | 复用原 pane，核对并更新 terminal ID | 复用原进程 | 条件支持；owner 中断需在宽限内恢复，超过约 20 秒会进入清理 |

还有三个横跨上述场景的限制：显式 Pause 或熔断后只恢复面板，需 Start 恢复 Gateway；基础 config.json、解释器、依赖、绑定或账本异常可能让完整 Dashboard 无法建立，但系统 Python 的恢复页仍可说明原因，具体可修复范围见 14.9；30 秒配置重试和 5 秒 renderer 重试都依赖 supervisor 仍存活，恢复页的 5 秒诊断刷新不会自动执行修复。

离线用例覆盖干净冷恢复、handoff 身份延续、owner 失联、孤儿进程和未知创建结果；Herdr 源码核对确认客户端断开保留 server，以及普通启动/handoff 启动执行 startup hook。本机已验证 cherry READY、Discord connected、真实面板与 monitor 复用；本轮没有重启用户正在使用的 Herdr 或电脑。恢复提示和原生弹窗另以临时 Herdr session 做了真实冷重启验收，范围见 14.9；cherry 的 detach/attach、server 重启及 handoff 不在本轮实测范围内。对应代码见 [manifest](../herdr-plugin.toml)、[controller](../src/hermes_gateway_herdr/controller.py)、[supervisor](../src/hermes_gateway_herdr/supervisor.py) 和 [生命周期测试](../tests/test_controller.py)。

## 14.6 测试与测量

0.1.0 的完整离线回归 **167 项通过**，见 [完整输出](evidence/release-0.1.0-unittest.txt)，包含 macOS 退出竞态及 HTTP 健康面板。原有面板阶段的 [153 项记录](evidence/dashboard-unittest.txt)及以下资源测量保留。

新增测试覆盖身份伪造和 PID 复用、慢 socket、轮询公平性和上限、共享 Gateway 计数、CPU 时间差及历史长度、1/2/25 个 profile 的多尺寸布局、过滤和滚动定位、偏好文件安全、真实 PTY 输入与 resize、失焦降频、高频按键不加快采样，以及面板退出／崩溃／阻塞对 Gateway 生命周期的隔离。配置和状态文件的 FIFO 回归使用真实 launcher 验证。

常驻 dashboard 回归验证旧 `auto_open=false` 仍直接打开完整监控、真实鼠标和 Enter 控制、暂停／熔断后保留同一 supervisor 与 pane、renderer 崩溃恢复、启动受阻后修正配置自动恢复，以及 Pause 前的迟到检查不能启动新的 Gateway。保存偏好失败仍显示提示且不覆盖不安全文件。

动画测试验证真实 PTY 中画面帧增加时采样次数不增加，静态模式和失焦停止额外绘制；渲染测试验证原图完整位于 SYSTEM 上方，动画只改变字符图的颜色。复用画面仍保留鼠标区域，主题、尺寸、选中项、新观测和观测过期都会使缓存失效，过期信息不会继续显示连接成功或当前资源值。状态文件在路径 stat 与 fd 检查期间发生原子替换均有回归覆盖，保留所有权、权限、硬链接和锁校验。

```sh
/absolute/path/to/hermes/venv/bin/python -I -B tests/run.py
```

以下为 **2026-09-12 旧版状态页与监控的历史测量**；状态页现已删除。这些数字不是本次常驻版本的性能验收。在 macOS arm64、Python 3.11.15、160×44 终端上，各阶段测量 20 秒，预热后计数。CPU 包含渲染、采样、原生 RPC 和进程指标读取；内存是面板进程 RSS。supervisor、被监控服务和测试工具的资源未计入。对端全部使用临时目录与本地假 Gateway。

| profile 数 | 状态 | CPU，单核口径 | RSS 中位数 | 终端输出 |
| --- | --- | --- | --- | --- |
| 2 | 默认状态页 | 0.239% | 35.86 MiB | 0 B/s |
| 2 | 完整监控 | 0.582% | 35.92 MiB | 876 B/s |
| 2 | 失焦 | 0.052% | 35.97 MiB | 0 B/s |
| 50 | 默认状态页 | 0.255% | 35.50 MiB | 0 B/s |
| 50 | 完整监控 | 0.914% | 35.58 MiB | 1035 B/s |
| 50 | 失焦 | 0.058% | 35.61 MiB | 0 B/s |

两种规模下，默认状态页对其他 profile 的原生请求均为 **0**。50 profile 的完整监控在这一有限观察窗口内覆盖了 39 个后台 profile，余下按有界轮询继续检查。

同尺寸、90 个历史样本的完整画面重绘中位数：1/2/50/1000 条 profile 分别为 6.03/7.10/8.75/10.16 ms；复用画面后的动画帧分别为 0.78/0.79/0.79/0.78 ms。这两项只测 hqtui framebuffer 构造与绘制，不包括终端编码和输出；上表的完整进程测量包含这些开销。原始数字和测量范围见 [JSON 记录](evidence/dashboard-benchmark.json)。

```sh
/absolute/path/to/hermes/venv/bin/python -I -B tools/dashboard_benchmark.py \
  --profiles 2 50 --seconds 20 --output /tmp/dashboard-benchmark.json
```

## 14.7 查看与启用

不连接真实服务的 HTML 预览：

```sh
/absolute/path/to/hermes/venv/bin/python -I -B tools/dashboard_preview.py \
  --profiles 2 --width 160 --height 44 --output /tmp/hermes-on-herdr.html
```

添加 `--pose 1` 或 `--pose 2` 可导出双蛇杖不同色彩阶段；HTML 是静态 framebuffer 预览，动画在 TTY 中运行。

已有有效插件配置时，可以独立运行演示 TUI；此模式不会构造真实采样器：

```sh
./bin/hermes-on-herdr --config /absolute/config.json dashboard --demo-profiles 2
./bin/hermes-on-herdr --config /absolute/config.json dashboard --demo-profiles 20
```

真实只读监控入口，以及一次性文本／JSON 快照入口：

```sh
./bin/hermes-on-herdr --config /absolute/config.json dashboard
./bin/hermes-on-herdr --config /absolute/config.json dashboard --snapshot
./bin/hermes-on-herdr --config /absolute/config.json dashboard --json
```

独立 `dashboard` 可在普通 Herdr pane 中打开，保持只读及独立退出语义；旧 `--startup` 参数兼容接受，仍显示完整 dashboard。它不提供 Gateway 启停按钮。

恢复并聚焦插件自己的常驻 dashboard：

```sh
herdr plugin action invoke monitor --plugin nocoo.hermes-gateway
```

也可运行 `./bin/hermes-on-herdr --config /absolute/config.json --owner-socket /absolute/bound.sock monitor`。只切回面板不清除 Gateway 的暂停意图。

## 14.8 本机网页与健康检查

终端面板之外，可在另一个 Herdr pane 中启动独立的只读网页：

```sh
./bin/hermes-on-herdr --config /absolute/config.json dashboard --http-port 8767
curl --fail http://127.0.0.1:8767/health
```

命令保持前台运行，输出实际 URL。页面为 `http://127.0.0.1:8767/`；端口 `0` 会选择空闲端口。此模式不显示 TUI，不能与 `--startup`、`--snapshot`、`--json`、演示或嵌入选项混用。关闭它不会暂停或终止 Gateway；它不会安装系统服务，也不随插件默认启动。

网页只采样配置绑定的 Profile，复用原生身份和 supervisor 归属检查；独立采样器每两秒更新一次，HTTP 请求只读缓存，不增加 Gateway RPC。`/health` 仅在托管状态为 READY、Gateway PID 与 pane 可核验、期望平台全部 connected、采样不超过六秒时返回 **HTTP 200 / healthy=true**。未启动、断连、归属失败、采样失败或过期返回 **503**。页面本身返回 200 不代表 Gateway 健康。

服务只绑定 `127.0.0.1`，启动不做反向 DNS 查询；拒绝外部 Host/Origin，不提供控制接口，不读取或输出凭据。它是本机观察入口；不作为公开网络服务或跨用户认证边界。TUI 的多 Profile 布局与交互不变。

运行中的 supervisor 需要重新启动才能加载新的生命周期代码；只重启 Gateway child 不会更新 supervisor。完整宿主冷启动、退出清理和在线升级 handoff 的真实验收与历史证据以 [cherry 接入记录](13-cherry接入与验证.md) 为准，不能用模拟恢复测试替代。

品牌和新 checkout 使用 `hermes-on-herdr`，稳定的 plugin ID、配置目录和控制协议保持不变。开发目录重命名的兼容符号链接只处理路径一致性，相关兼容和错误目录拒绝已有回归测试；它不会把开发 link 变成正式安装。从开发 link 迁入 Release 或升级发布版本时，按[发布与安装](15-发布与安装.md)完成停止、来源替换和验证，再启动新 supervisor 与独立面板。

## 14.9 故障恢复入口

0.1.2 提供 `hermes-on-herdr` 无参数恢复入口。配置位置自动取自 Herdr 的插件环境或默认 / XDG 配置目录；用户不必填写 Profile、session、socket 等参数。shell 命令只需在安装时[建立一次链接](15-发布与安装.md#恢复命令的安装)。Herdr 命令面板中的 **hermes on herdr: Recovery & Repair** 使用原生插件 popup 打开同一恢复页。

正常创建或显式打开已核验的专属面板后，插件保存 tab 名称 `Hermes · 恢复: hermes-on-herdr`，并在 pane 标签留下：

> Dashboard 未就绪？运行 hermes-on-herdr 查看原因并恢复。

Herdr 会将这两个字段写入 session 快照；冷启动把原 pane 恢复为 shell 时，提示仍在。它是一条恢复入口提示，不代表当前健康状态。未保存的快照、整个 workspace 被删除、Herdr 状态目录丢失时无法保证留下文字；Herdr server 尚未启动时，workspace 本身也不可见，仍可从外部 shell 使用恢复命令。

恢复页由系统 `/usr/bin/python3 -IS` 和标准库 curses 运行，展示 Profile、当前状态、失败检查和下一步；每 5 秒做一次有界诊断。完整 Dashboard 所需的虚拟环境、psutil、PyYAML、hqtui 不参与恢复页自身的加载。`supervise` 在交互 pane 中因 bootstrap、导入或初始化失败退出时，以同一个根 PID 切换到恢复页。恢复页退出不会暂停 Gateway。

| 情况 | 恢复页提供的操作 | 保留的边界 |
| --- | --- | --- |
| Dashboard 不在，正常管理状态可读 | 恢复 / 打开 Dashboard | 复用原实例；不清除 Pause 或熔断 |
| 旧创建请求残留，原控制器已退出 | 恢复 Dashboard 撤销旧请求并重新创建 | 同时持有 mutation 与 lifetime 锁；迟到旧 pane 不能启动 Gateway |
| Gateway 暂停、熔断或配置已修复 | 启动 / 重试 Gateway | 用观察到的 revision 提交 Start，拒绝覆盖较新的操作 |
| runtime-python 缺失或内容不一致，配置中的 Python 仍可用 | 修复 Python 入口并恢复 Dashboard | 原子写入 0600 的提示文件；不改 config.json 或 Profile，不替换 symlink / FIFO |
| 插件 Python 依赖缺失 | 修复插件依赖并恢复 Dashboard | 仅点击后安装 requirements，要求配置解释器属于 venv；不自动更改 Hermes 插件配置 |
| Herdr server 未运行，使用外部终端 | 打开 Herdr | 交给 Herdr 原生启动 / attach 流程，使用保存的 session/socket；不创建 OS service |
| ORPHAN、启动登记未完成、归属不明 | 说明原因、重新检查；正常 ensure 仍可核对实例 | 不提供强制杀进程或清空锁 / 账本的按钮 |
| 配置 / 绑定损坏、解释器文件丢失 | 显示原因和配置位置 | 需要恢复对应配置或安装，不能凭残缺数据猜测新绑定 |

原有脚本命令保持 JSON 契约。恢复页可用 `hermes-on-herdr recover --snapshot` 输出一帧文字，或用 `recover --json` 输出诊断和当前可用操作；非交互终端自动使用文字快照。系统 Python、插件源文件自身缺失时需先恢复安装；系统未提供 curses 时仍能打印文字诊断。

隔离回归见 [test_recovery.py](../tests/test_recovery.py)，覆盖无依赖加载、损坏配置、入口修复、私有文件保护、暂停 / 熔断保留、旧请求撤销、原生 popup 请求以及真实 PTY 的失败回退和退出恢复。依赖安装及 Herdr 启动按钮使用替身验证参数，不会在单元测试中安装软件或启动用户的 server。

2026-09-14 另使用原生 Herdr 0.9.0 和独立临时配置目录，验证 manifest 加载、失败 supervisor 显示恢复页、真实 TUI 客户端中的原生 popup，以及同一测试 session 冷重启后仍保留 tab / pane 提示，见 [原生验收记录](evidence/recovery-native.txt)。测试 session 没有关联真实 Profile，证明的是恢复入口和提示持久性，不代表 cherry Gateway 已经过真实宿主重启验收。

本次 Python 3.11 / 3.14 完整回归各 **206 项通过**，包括真实空 venv 的依赖导入失败回退；命令和结果摘要见 [验证记录](evidence/recovery-validation.txt)。本机安装后已核验无参数入口、Herdr Recovery & Repair 动作及持久快照中的提示；cherry 的 supervisor / Gateway PID 和运行意图保持不变，仍为 READY。

返回 [文档索引](README.md) · [cherry 接入记录](13-cherry接入与验证.md)。
