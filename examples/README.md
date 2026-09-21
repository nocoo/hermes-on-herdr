# Plugin configuration

[config.example.json](config.example.json) lists the plugin configuration fields. Replace the absolute placeholder paths with an existing named Hermes Profile, its Python environment, Hermes executable, Herdr executable and owner session socket. `expected_platforms` identifies the connections used by the readiness monitor.

The Profile and private plugin configuration directories must be owned by the current user with mode `0700`. `config.json` and `runtime-python` use `0600`; the latter contains exactly the configured `python_bin` absolute path. Keep the virtual environment interpreter path rather than resolving it to a system Python.

Configure Hermes itself with Hermes. There is no plugin policy template for `config.yaml`: models, tools such as `connections`, plugins, MCP, terminal backend, hooks and keepalive are Hermes settings. The plugin does not read or modify that file. It supplies the selected Profile and Herdr pane environment and prevents `.env` from overriding only the launch ownership fields described in [compatibility](../docs/18-Herdr兼容策略.md#hermes-gateway-contract).

```sh
./bin/hermes-on-herdr --config /absolute/config.json bind --dry-run
./bin/hermes-on-herdr --config /absolute/config.json bind --apply
./bin/hermes-on-herdr --config /absolute/config.json start
```

`bind` defaults to a read-only plan. Applying it initializes only the plugin control directory with paused intent. Repeated binding preserves existing intent and fuse state. Start explicitly permits the configured Gateway to run. Installation, upgrade and recovery are documented in the [release guide](../docs/15-发布与安装.md).
