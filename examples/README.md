# 配置审阅材料

这些模板没有被应用到任何用户 Profile。真实配置、独立 bot 凭据和插件安装仍待确认。

[config.example.json](config.example.json) 是当前插件配置字段全集，路径均为占位符。`profile_home` 必须解析为一个已存在、权限为0700的 `<root>/profiles/herdr-control`；解释器要保留 venv 中的路径，不能改写成 symlink 的系统目标。配置目录为0700，`config.json` 与 `runtime-python` 均为0600，后者只含与 `python_bin` 一致的一行绝对路径。

[profile-policy.yaml](profile-policy.yaml) 仅展示预检要求，不是完整可运行 Profile。provider/model、cwd、期望平台、独立凭据及平台用户访问策略需要明确配置并验证。新 Profile 的空白暂存创建/迁入流程见 [04](../docs/04-Hermes专用Profile设计.md)，本轮尚未实现该初始化器。不要将模板覆盖到现有用户配置。

`bind` 默认 dry-run；只有 `bind --apply` 才创建控制目录，初始意图为 paused。绑定不会启动 Gateway、修改 `active_profile`、复制凭据或安装服务。目录已绑定时重复执行不会清除暂停和熔断。完整命令说明及离线证据见 [12](../docs/12-离线实现与验证.md)。
