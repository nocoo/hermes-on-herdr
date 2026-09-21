"""A small recovery UI that runs on OS Python without Hermes, YAML or psutil."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unicodedata
import uuid

from .bootstrap import PLUGIN_ID, RECOVERY_HINT, RECOVERY_TAB, ROOT, read_config, runtime_argv
from .compatibility import check_herdr_compatibility
from .errors import GatewayError
from .paths import check_private, json_object, private_bytes, trusted_path
from .transport import exchange

MESSAGES = {
    "READY": ("Gateway 已连接。", "可以直接打开 Dashboard。"),
    "PAUSED": ("Gateway 已暂停；Dashboard 仍可打开。", "需要运行时，点击启动 Gateway。"),
    "ABSENT": ("Dashboard 尚未运行。", "点击恢复 Dashboard，将按之前的运行或暂停设置恢复。"),
    "STARTING": ("Gateway 正在启动。", "稍候，状态会自动更新；也可以打开 Dashboard。"),
    "PENDING": ("Dashboard 正在创建。", "稍候再检查；恢复按钮会核对已有实例。"),
    "BACKOFF": ("Gateway 正在等待重试。", "可以等待自动恢复，或点击启动 / 重试。"),
    "DEGRADED": ("Gateway 尚未连接所有平台。", "打开 Dashboard 查看连接状态，检查平台和网络设置。"),
    "DRAINING": ("旧 Gateway 正在退出。", "等待退出完成后，再恢复 Dashboard。"),
    "FUSED": ("Gateway 因连续失败已停止自动重试。", "检查配置后，点击启动 / 重试解除暂停重试。"),
    "BLOCKED": ("Gateway 启动检查未通过。", "修正下方失败项后点击启动 / 重试；Dashboard 可以保持打开。"),
    "PENDING_UNKNOWN": ("上次创建 Dashboard 的结果未确认。", "点击恢复 Dashboard；确认旧控制器已退出后会撤销旧请求并重建。"),
    "UNKNOWN": ("暂时无法确认旧进程是否仍在运行。", "先重新检查；归属确认前不会重复启动或清理进程。"),
    "ORPHAN": ("检测到仍在运行、但已失去面板管理的 Gateway。", "需要先确认旧实例已经退出；此处不会强制结束或重复启动。"),
    "SPAWN_UNCONFIRMED": ("上次启动在进程登记完成前中断，无法确认是否留下了 Gateway。", "需要检查旧进程及启动记录；不会自动清空状态或并行启动。"),
    "SETUP_REQUIRED": ("尚未找到完整的插件关联配置。", "恢复已有 config.json / 关联状态后重新检查；配置位置见下方。"),
    "CONFIG_ERROR": ("插件配置或 Python 入口不可用。", "修复下方配置；若提供了修复入口按钮，可以直接使用。"),
    "UNSAFE_PATH": ("配置或状态文件的类型、权限不符合要求。", "检查文件应为普通文件且权限 0600，配置目录为 0700。"),
    "DEPENDENCY_MISSING": ("插件所需的 Python 依赖缺失。", "点击修复插件依赖，再恢复 Dashboard。"),
    "DEPENDENCY_REPAIR_FAILED": ("插件依赖安装未完成。", "检查网络和 Hermes 环境中的 pip，然后再试。"),
    "PYTHON_VERSION": ("配置的 Python 版本不受支持。", "恢复 Hermes 的 Python 3.11 或更新版本环境后重新检查。"),
    "RPC_UNAVAILABLE": ("暂时无法连接 Herdr server。", "外部终端可点击打开 Herdr，启动或连接原来的 session。"),
    "OWNER_UNAVAILABLE": ("暂时无法连接 Herdr server。", "外部终端可点击打开 Herdr，启动或连接原来的 session。"),
    "DISABLED": ("此 Herdr 插件已停用。", "在 Herdr 插件管理中启用 hermes on herdr，再重新检查。"),
    "STATE_SCHEMA": ("保存的管理状态不完整或版本不兼容。", "恢复管理状态的备份后重新检查；不会自动清空绑定或锁。"),
    "OWNERSHIP_CONFLICT": ("配置与原来的 Profile 或插件绑定不一致。", "恢复原绑定配置后重新检查。"),
    "NOT_OWNER": ("当前 Herdr session 不是此 Profile 的管理者。", "请在原来的 session，或外部终端运行 hermes-on-herdr。"),
    "STALE_REQUEST": ("运行设置刚刚被其他操作更新。", "已保留较新的设置；重新检查后再操作。"),
    "RECOVERY_TIMEOUT": ("本次检查未在期限内完成。", "可以重新检查；若持续失败，请检查运行环境。"),
    "IO_ERROR": ("操作未能完成。", "重新检查下方状态，再决定下一步。"),
}


def clean(value, limit=300):
    return "".join(char for char in str(value) if char.isprintable())[:limit]


def owner_environment(data, owner_socket=None):
    socket = data.get("owner_socket")
    if not isinstance(socket, str) or not Path(socket).is_absolute() or any(ord(c) < 32 for c in socket):
        raise GatewayError("CONFIG_ERROR")
    inherited = owner_socket or os.environ.get("HERDR_SOCKET_PATH")
    if inherited and Path(inherited).resolve() != Path(socket).resolve():
        raise GatewayError("NOT_OWNER")
    return dict(os.environ, HERDR_SOCKET_PATH=socket)


def invoke(config, command, *, arguments=(), owner_socket=None):
    data = read_config(config)
    env = owner_environment(data, owner_socket) if command != "doctor" else dict(os.environ)
    argv = runtime_argv(config, [command, *arguments])
    try:
        result = subprocess.run(argv, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=6)
    except subprocess.TimeoutExpired as exc:
        raise GatewayError("RECOVERY_TIMEOUT") from exc
    if len(result.stdout) > 256 * 1024:
        raise GatewayError("PROTOCOL_ERROR")
    return json_object(result.stdout)


def hint_target(config):
    data = read_config(config)
    if data.get("schema") != 1 or trusted_path(data.get("plugin_root"), directory=True).resolve() != ROOT:
        raise GatewayError("CONFIG_ERROR")
    interpreter = trusted_path(data.get("python_bin"))
    if not os.access(interpreter, os.X_OK):
        raise GatewayError("CONFIG_ERROR")
    hint = config.parent / "runtime-python"
    try:
        check_private(hint.lstat())
    except FileNotFoundError:
        return data, interpreter, None
    return data, interpreter, private_bytes(hint, 4096)


def repair_hint(config):
    data, interpreter, previous = hint_target(config)
    fd, temporary = tempfile.mkstemp(prefix=".runtime-python-", dir=config.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write((str(interpreter) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())
        if hint_target(config) != (data, interpreter, previous):
            raise GatewayError("STALE_REQUEST")
        os.replace(temporary, config.parent / "runtime-python")
        directory = os.open(config.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def diagnose(config, *, owner_socket=None):
    data, checks, runtime, actions = {}, [], {}, []
    try:
        data = read_config(config)
        observed = invoke(config, "doctor")
        runtime = observed.get("runtime", {})
        checks = observed.get("checks", [])
        state = runtime.get("state", observed.get("state", "ERROR"))
        code = observed.get("code") or runtime.get("code") or state
        failed = next((item for item in checks if not item.get("ok")), None)
        if failed and state not in {"ORPHAN", "PENDING_UNKNOWN", "FUSED"}:
            code = failed.get("code", code)
        if observed.get("state") == "DIAGNOSIS":
            owner_environment(data, owner_socket)
            actions.append({"id": "monitor", "label": "恢复 / 打开 Dashboard"})
            if state not in {"ORPHAN", "UNKNOWN", "DRAINING"} and type(runtime.get("intent_revision")) is int:
                actions.append({"id": "start", "label": "启动 / 重试 Gateway"})
            owner_check = next((item for item in checks if item.get("name") == "owner"), {})
            if (not os.environ.get("HERDR_PANE_ID") and not os.environ.get("HERDR_ENV")
                    and owner_check.get("code") in {"OK", "DISABLED", "RPC_UNAVAILABLE"}):
                actions.append({"id": "attach", "label": "打开 Herdr（自动启动或连接原 session）"})
        elif code == "DEPENDENCY_MISSING":
            owner_environment(data, owner_socket)
            actions.append({"id": "dependencies", "label": "修复插件依赖并恢复 Dashboard"})
    except (GatewayError, OSError, ValueError, UnicodeError) as exc:
        state, code = "ERROR", exc.code if isinstance(exc, GatewayError) else "IO_ERROR"
        actions = []
    try:
        _, interpreter, previous = hint_target(config)
        if code != "NOT_OWNER" and previous != (str(interpreter) + "\n").encode():
            actions.insert(0, {"id": "hint", "label": "修复 Python 入口并恢复 Dashboard"})
    except (GatewayError, OSError, ValueError, UnicodeError):
        pass
    reason, next_step = MESSAGES.get(code, MESSAGES.get(state, ("检查未通过。", "修复失败项后重新检查。")))
    return {"schema": 1, "state": state, "code": code, "reason": reason, "next_step": next_step,
            "profile": clean(data.get("profile_id", "未关联")), "configuration": str(config),
            "checks": [{"name": clean(item.get("name", "")), "ok": item.get("ok") is True,
                        "code": clean(item.get("code", "")), "message": clean(item.get("message", ""))}
                       for item in checks],
            "runtime": runtime, "actions": actions}


def perform(config, action, report, *, owner_socket=None):
    if action not in {item["id"] for item in report["actions"]}:
        raise GatewayError("INVALID_ARGUMENT")
    owner_environment(read_config(config), owner_socket)
    if action == "hint":
        repair_hint(config)
    elif action == "dependencies":
        argv = runtime_argv(config, [])
        requirements = trusted_path(str(ROOT / "requirements.txt"))
        try:
            result = subprocess.run([argv[0], "-I", "-B", "-m", "pip", "install", "--require-virtualenv",
                                     "--no-input", "--disable-pip-version-check", "-r", str(requirements)],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=120)
        except subprocess.TimeoutExpired as exc:
            raise GatewayError("RECOVERY_TIMEOUT") from exc
        if result.returncode:
            raise GatewayError("DEPENDENCY_REPAIR_FAILED")
    arguments = ()
    if action == "start":
        arguments = ("--request-id", uuid.uuid4().hex, "--expected-revision", str(report["runtime"]["intent_revision"]))
    return invoke(config, "start" if action == "start" else "monitor", arguments=arguments, owner_socket=owner_socket)


def attach(config, *, owner_socket=None):
    # Use Herdr's own launch/attach flow, including server singleton and session restore.
    report = diagnose(config, owner_socket=owner_socket)
    if "attach" not in {item["id"] for item in report["actions"]}:
        raise GatewayError("NOT_OWNER")
    data = read_config(config)
    env = owner_environment(data, owner_socket)
    for key in list(env):
        if key.startswith(("HERDR_", "HGH_")) and key not in {"HERDR_SOCKET_PATH", "HERDR_CONFIG_PATH"}:
            del env[key]
    env["HERDR_SESSION"] = data["owner_session"]
    binary = trusted_path(data["herdr_bin"])
    os.execve(str(binary), [str(binary)], env)


def remember_hint(client, pane):
    # Only call with a newly created or process-verified plugin pane. Titles are
    # persisted by Herdr; they are a breadcrumb, never proof of current liveness.
    try:
        client.call("tab.rename", {"tab_id": pane["tab_id"], "label": RECOVERY_TAB})
        client.call("pane.rename", {"pane_id": pane["pane_id"], "label": RECOVERY_HINT})
    except GatewayError:
        pass  # A cosmetic failure must not invalidate a confirmed creation ticket.


def open_popup(config, *, owner_socket=None):
    socket = owner_socket or os.environ.get("HERDR_SOCKET_PATH")
    if not socket:
        socket = read_config(config).get("owner_socket")
    if not isinstance(socket, (str, Path)) or not Path(socket).is_absolute():
        raise GatewayError("NOT_OWNER")
    def call(method, params):
        response = exchange(Path(socket), {"id": uuid.uuid4().hex, "method": method, "params": params})
        if "error" in response or not isinstance(response.get("result"), dict):
            raise GatewayError("HERDR_ERROR")
        return response["result"]
    check_herdr_compatibility(call("ping", {}))
    plugins = call("plugin.list", {"plugin_id": PLUGIN_ID}).get("plugins", [])
    if not isinstance(plugins, list):
        raise GatewayError("PROTOCOL_ERROR")
    matching = [item for item in plugins if isinstance(item, dict) and item.get("plugin_id") == PLUGIN_ID]
    if len(matching) != 1 or trusted_path(matching[0].get("plugin_root"), directory=True).resolve() != ROOT:
        raise GatewayError("OWNERSHIP_CONFLICT")
    if matching[0].get("enabled") is not True:
        raise GatewayError("DISABLED")
    return call("plugin.pane.open", {"plugin_id": PLUGIN_ID, "entrypoint": "recovery",
                                    "placement": "popup", "focus": True})


def lines(report):
    result = ["hermes on herdr · 恢复中心", f"Profile: {report['profile']}    状态: {clean(report['state'])}",
              "", report["reason"], report["next_step"], ""]
    names = {"profile": "Profile 配置", "owner": "Herdr server"}
    for check in report["checks"]:
        result.append(f"{'✓' if check['ok'] else '×'} {names.get(check['name'], check['name'])}: {check['code']}")
        if not check["ok"] and check["message"]:
            result.append("  " + check["message"])
    return [*result, "", "配置: " + clean(report["configuration"]), ""]


def screen_ui(screen, config, owner_socket):
    import curses
    curses.curs_set(0)
    curses.mousemask(curses.ALL_MOUSE_EVENTS)
    screen.timeout(100)
    selected, message, refreshed, closing = 0, "正在检查…", time.monotonic(), False
    report = {"profile": "…", "state": "CHECKING", "reason": "", "next_step": "", "checks": [],
              "configuration": str(config), "actions": []}
    def work(action=None):
        note = ""
        if action:
            try:
                result = perform(config, action, report, owner_socket=owner_socket)
                code = result.get("code") or result.get("state", "IO_ERROR")
                note = "Dashboard 已打开。" if result.get("pane") else (
                    "启动请求已提交，正在核对实际状态。" if result.get("accepted") else MESSAGES.get(code, (clean(code), ""))[0])
            except (GatewayError, OSError, ValueError, UnicodeError) as exc:
                code = exc.code if isinstance(exc, GatewayError) else "IO_ERROR"
                note = MESSAGES.get(code, (clean(code), ""))[0]
        return diagnose(config, owner_socket=owner_socket), note
    # One worker keeps keyboard/mouse responsive during bounded CLI checks and pip.
    with ThreadPoolExecutor(max_workers=1) as worker:
        pending = worker.submit(work)
        while True:
            if pending and pending.done():
                report, message = pending.result()
                pending, refreshed = None, time.monotonic()
                if closing:
                    return None
            buttons = [*report["actions"], {"id": "refresh", "label": "重新检查"}, {"id": "quit", "label": "返回"}]
            selected = min(selected, len(buttons) - 1)
            screen.erase()
            height, width = screen.getmaxyx()
            def put(row, value, style=0):
                used, visible = 0, ""
                for char in clean(value, 1000):
                    used += 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
                    if used > width - 4:
                        break
                    visible += char
                if 0 <= row < height - 1:
                    try:
                        screen.addstr(row, 2, visible, style)
                    except curses.error:
                        pass
            body = lines(report)
            first_button = min(len(body), max(3, height - len(buttons) - 4))
            for row, value in enumerate(body[:first_button]):
                put(row, value, curses.A_BOLD if row == 0 else 0)
            for index, button in enumerate(buttons):
                put(first_button + index, "[ " + button["label"] + " ]", curses.A_REVERSE if index == selected else 0)
            put(height - 3, message or "状态每 5 秒更新；打开面板会保留原来的暂停设置。")
            put(height - 2, "↑↓ / Tab 选择 · Enter / 鼠标点击 · R 重新检查 · Q 返回")
            screen.refresh()
            key = screen.getch()
            choice = None
            if key in (ord("q"), ord("Q"), 27):
                choice = "quit"
            elif key in (curses.KEY_DOWN, 9):
                selected = (selected + 1) % len(buttons)
            elif key in (curses.KEY_UP, curses.KEY_BTAB):
                selected = (selected - 1) % len(buttons)
            elif key in (10, 13, curses.KEY_ENTER):
                choice = buttons[selected]["id"]
            elif key in (ord("r"), ord("R")):
                choice = "refresh"
            elif key == curses.KEY_MOUSE:
                try:
                    _, _, row, _, mask = curses.getmouse()
                    index = row - first_button
                    if mask & (curses.BUTTON1_CLICKED | curses.BUTTON1_RELEASED) and 0 <= index < len(buttons):
                        selected, choice = index, buttons[index]["id"]
                except curses.error:
                    pass
            if choice == "quit":
                if not pending:
                    return None
                closing, message = True, "正在完成已提交的操作，随后返回…"
            if not pending:
                if choice == "attach":
                    return "attach"
                if choice or time.monotonic() - refreshed >= 5:
                    message = "正在检查…" if choice in (None, "refresh") else "正在执行，请稍候…"
                    pending = worker.submit(work, None if choice in (None, "refresh") else choice)


def main(config, arguments=(), *, owner_socket=None):
    parser = argparse.ArgumentParser(prog="hermes-on-herdr recover", allow_abbrev=False)
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true")
    output.add_argument("--snapshot", action="store_true")
    output.add_argument("--open", action="store_true", help="Open recovery as a native Herdr popup")
    options = parser.parse_args(arguments)
    try:
        if options.open:
            print(json.dumps(open_popup(config, owner_socket=owner_socket)))
            return 0
        if options.json or options.snapshot or not (sys.stdin.isatty() and sys.stdout.isatty()) or os.environ.get("TERM") == "dumb":
            report = diagnose(config, owner_socket=owner_socket)
            print(json.dumps(report, ensure_ascii=False) if options.json else "\n".join(
                [*lines(report), *("[ " + item["label"] + " ]" for item in report["actions"]), RECOVERY_HINT]))
            return 0
        try:
            import curses
            action = curses.wrapper(screen_ui, config, owner_socket)
        except ImportError:
            print("\n".join(lines(diagnose(config, owner_socket=owner_socket))))
            print("当前系统没有 curses 终端组件；可用 recover --snapshot 查看诊断。")
            return 20
        except curses.error:
            print("\n".join(lines(diagnose(config, owner_socket=owner_socket))))
            return 20
        if action == "attach":
            attach(config, owner_socket=owner_socket)
        return 0
    except KeyboardInterrupt:
        return 0
    except (GatewayError, OSError, ValueError, UnicodeError) as exc:
        code = exc.code if isinstance(exc, GatewayError) else "IO_ERROR"
        print(json.dumps({"schema": 1, "state": "ERROR", "code": code,
                          "message": MESSAGES.get(code, (clean(code), ""))[0]}, ensure_ascii=False))
        return 20
