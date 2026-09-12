<p align="center">
  <img src="assets/brand/icon-rounded.png" width="128" alt="hermes on herdr logo" />
</p>
<h1 align="center">hermes on herdr</h1>
<p align="center">在 Herdr 中运行 Hermes，按需打开监控面板。</p>
<p align="center"><a href="docs/README.en.md">English</a> · <a href="docs/README.md">文档</a> · <a href="examples/README.md">配置示例</a></p>

**hermes on herdr** 是一个 Herdr 插件：让专用 Hermes Gateway 运行在真实 pane 内，由 supervisor 管理进程生命周期，并继承所属 Herdr session 的控制环境。运行意图、进程身份和所有权都有记录，暂停后需要明确恢复。

![hermes on herdr 双 Profile 监控面板，使用离线演示数据](docs/evidence/dashboard-two.png)

## 使用体验

- 启动时先显示专用 Gateway 的状态，按 **Enter** 打开完整监控；“以后自动打开”默认关闭，可用空格或鼠标保存选择。
- 监控面板展示多个 Hermes Profile 的状态、CPU、内存和进程趋势，突出 Herdr 专属实例。布局、主题、动画与采样频率均可调整，默认每两秒采样。
- `start`、`pause`、`resume`、`stop` 和 `restart` 管理 Gateway；`status`、`doctor` 和 `logs` 提供 JSON 诊断。
- supervisor 使用单例锁、身份核验、有界重试和熔断；遇到未知启动结果或仍存活的孤儿进程时，会先保留现场供诊断。

面板预览、快捷键和资源测量见 [监控面板指南](docs/14-hqtui监控面板.md)。

## 上手

当前为开发版，使用 Python 3.11+ 和已配置的 Hermes 虚拟环境。运行依赖是 [psutil 与 PyYAML](requirements.txt)，固定版本的 hqtui 源码随仓库提供。已验证的宿主基线是 Herdr v0.9.0、Hermes Agent v0.21.1；完整版本与提交见 [源码证据](docs/09-源码证据索引.md)。

```sh
git clone https://github.com/nocoo/hermes-on-herdr.git
cd hermes-on-herdr
./bin/hermes-on-herdr --help
```

帮助命令无需配置。接入前，按 [配置示例](examples/README.md) 准备独立 Herdr session、已有的专用 Hermes Profile 和私有配置目录。安装与接入步骤见 [实现及验收计划](docs/05-实现步骤.md)，当前没有自动创建 Profile 的安装器。

准备配置后，将下面的占位路径替换为实际 `config.json`：

```sh
./bin/hermes-on-herdr --config /absolute/config.json status --json
./bin/hermes-on-herdr --config /absolute/config.json doctor --json
./bin/hermes-on-herdr --config /absolute/config.json bind --dry-run
./bin/hermes-on-herdr --config /absolute/config.json dashboard
```

配置目录权限为 `0700`；`config.json` 和 `runtime-python` 为 `0600`。解释器提示文件只保存一行绝对路径，与配置的 `python_bin` 一致。

## 常用操作

以下命令均接在 `./bin/hermes-on-herdr --config /absolute/config.json` 后：

| 命令 | 行为 |
| --- | --- |
| `bind --dry-run` | 查看已有专用 Profile 的绑定计划；也是 `bind` 的默认行为 |
| `bind --apply` | 创建控制目录，初始暂停；随后显式 `start` 才允许运行 |
| `start` / `resume` | 保存运行意图并执行 ensure；收到 ACK 后仍需检查 READY |
| `pause` / `stop` | 先保存暂停意图，再通知 supervisor |
| `stop --wait 30` | 最多等待 30 秒，核验退出完成后报告结果 |
| `restart` | 对允许运行的实例请求重启，保留已有暂停意图 |
| `status --require-ready` | 仅在身份、运行状态及期望平台满足 READY 时成功 |
| `logs --lines 50` | 查看结构化生命周期事件 |
| `dashboard --startup` | 显示启动状态页，按需进入完整监控 |
| `dashboard --snapshot` / `dashboard --json` | 输出一次文本或 JSON 监控快照 |
| `dashboard --demo-profiles 2` | 使用合成数据预览双 Profile 面板 |

从 hook 外执行控制命令时，用全局 `--owner-socket /absolute/bound.sock` 指定绑定的 owner。全部参数、返回码与重试规则见 [命令契约](docs/12-离线实现与验证.md#124-当前命令契约)。

## 开发与验证

```sh
/absolute/path/to/hermes/venv/bin/python -I -B tests/run.py
```

测试使用临时目录、假 Herdr RPC、受控 Gateway 进程和真实 PTY，不调用已安装的 Herdr／Hermes 入口。最近保存的 [153 项离线测试](docs/evidence/dashboard-unittest.txt) 覆盖生命周期竞态、身份核验、监控采样、启动偏好、终端输入及渲染故障隔离；资源测量见 [监控面板指南](docs/14-hqtui监控面板.md#146-测试与测量)。

cherry 曾在插件监管下达到 READY，消息连通已获用户确认；独立面板也完成了真实只读预览。嵌入启用、冷启动、退出清理、指定 pane 的双向交互、Linux 和 live handoff 的验证状态见 [接入记录](docs/13-cherry接入与验证.md)。READY 表示进程及平台就绪，不等于模型调用或消息端到端验证。

## 文档

- [文档索引](docs/README.md)：按使用、开发和研究选择阅读路径，查看当前验证范围。
- [配置示例](examples/README.md)：解释器、专用 Profile、私有目录和绑定规则。
- [监控面板](docs/14-hqtui监控面板.md)：启动页、布局、快捷键、采样与性能。
- [安全与运维](docs/07-安全与运维.md)：权限、诊断、暂停和升级边界。
- [系统架构](docs/02-系统架构.md)与[生命周期](docs/03-生命周期设计.md)：controller、supervisor、锁和恢复协议。
- [品牌与标识](assets/brand/README.md)：Logo 用法、原始来源及 Hexly 展示。

品牌为 **hermes on herdr**，仓库和命令名为 `hermes-on-herdr`。内部标识与历史命名见 [文档约定](docs/README.md#命名约定)。
