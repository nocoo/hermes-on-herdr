# hermes on herdr 配置示例

这些文件用于配置已有的专用 Hermes Profile。项目入口是 `bin/hermes-on-herdr`；先运行 `--help`，再准备自己的私有配置目录。真实 cherry 接入与验证记录见 [13](../docs/13-cherry接入与验证.md)。

| 文件 | 用途 |
| --- | --- |
| [config.example.json](config.example.json) | 当前插件字段全集，所有路径均为占位符 |
| [profile-policy.yaml](profile-policy.yaml) | Profile 预检要求，需结合实际 provider、model、平台与访问策略补全 |

`profile_home` 指向已存在、权限为 `0700` 的专用 Profile。解释器保留 Hermes venv 中的路径，不改写成 symlink 的系统目标。配置目录为 `0700`，`config.json` 与 `runtime-python` 为 `0600`；后者只包含与 `python_bin` 一致的一行绝对路径。

专用 Profile 的独立凭据、工作目录和期望平台需先配置好；初始化设计见 [04](../docs/04-Hermes专用Profile设计.md)。当前没有自动创建 Profile 的工具，示例不是可直接覆盖已有用户配置的完整文件。

Hermes 自身的插件配置和加载开关由 Hermes 管理，本项目不检查 `plugins` 的内容，也不强制设置 `HERMES_ENABLE_PROJECT_PLUGINS`。运行配置检查失败会在常驻 dashboard 中显示检查项并每 30 秒重试；修正配置后可自动启动，也可点击 Start 立即重试。

```sh
./bin/hermes-on-herdr --config /absolute/config.json bind --dry-run
```

`bind` 默认展示计划。`bind --apply` 创建控制目录，初始意图为 paused；之后用显式 `start` 允许运行。重复绑定保留既有暂停和熔断状态。绑定不会创建 Profile、复制凭据或安装系统服务。所有控制参数及返回码见 [命令契约](../docs/12-离线实现与验证.md#124-当前命令契约)。
