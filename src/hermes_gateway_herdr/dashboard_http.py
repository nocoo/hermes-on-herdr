"""Optional loopback status page. Requests only read one bounded monitor sample."""

from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from socketserver import TCPServer
import threading
import time

from . import __version__
from .monitor import Monitor, Snapshot


class DashboardServer(HTTPServer):
    def __init__(self, config, port):
        self.config = config
        self.monitor = Monitor(config, host=False)
        self.latest = (Snapshot(), 0.0)
        super().__init__(("127.0.0.1", port), DashboardHandler)
        self.url = f"http://127.0.0.1:{self.server_port}"

    def server_bind(self):
        # HTTPServer resolves getfqdn() here, which can stall on macOS DNS.
        # This listener has a fixed numeric address and needs no name lookup.
        TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(0.5)
        return connection, address

    def sample(self):
        started = time.monotonic()
        try:
            snapshot = self.monitor.collect(managed_only=True)
        except Exception:
            snapshot = Snapshot(error="COLLECTOR_UNAVAILABLE")
        self.latest = (snapshot, started)

    def health(self):
        snapshot, sampled = self.latest
        profile = next((p for p in snapshot.profiles if p.managed and p.name == self.config.profile_id), None)
        age = time.monotonic() - sampled if sampled else None
        fresh = age is not None and 0 <= age <= 6
        platforms = dict(profile.platforms) if profile else {}
        healthy = bool(fresh and not snapshot.error and profile and not profile.error
                       and profile.state == "READY" and profile.pid and profile.pane
                       and all(platforms.get(p) == "connected" for p in self.config.expected_platforms))
        return {"schema": 1, "version": __version__, "healthy": healthy, "profile": self.config.profile_id,
                "owner_session": self.config.owner_session, "state": profile.state if profile else "UNKNOWN",
                "gateway_pid": profile.pid if profile else None, "pane": profile.pane if profile else "",
                "supervision": profile.supervision if profile else "unknown", "platforms": platforms,
                "cpu_percent": profile.cpu if profile else None, "rss_bytes": profile.rss if profile else None,
                "sample_age_seconds": round(age, 3) if age is not None else None,
                "error": "STALE_SAMPLE" if not fresh else snapshot.error or (profile.error if profile else "NO_PROFILE")}


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        server = self.server
        hosts = {f"127.0.0.1:{server.server_port}", f"localhost:{server.server_port}"}
        if self.headers.get("Host") not in hosts or (
                self.headers.get("Origin") is not None and self.headers["Origin"] not in {f"http://{h}" for h in hosts}):
            self.send_error(403)
            return
        if self.path not in {"/", "/health"}:
            self.send_error(404)
            return
        data = server.health()
        if self.path == "/health":
            status = 200 if data["healthy"] else 503
            content_type = "application/json"
            body = json.dumps(data, allow_nan=False)
        else:
            status, content_type = 200, "text/html; charset=utf-8"
            fields = {"Profile": data["profile"], "Status": data["state"],
                      "Health": "Ready" if data["healthy"] else data["error"] or "Not ready",
                      "Herdr session": data["owner_session"], "Pane": data["pane"],
                      "Gateway PID": data["gateway_pid"], "Supervisor": data["supervision"],
                      "Platforms": ", ".join(f"{k}: {v}" for k, v in data["platforms"].items()),
                      "CPU": f'{data["cpu_percent"]:.1f}%' if data["cpu_percent"] is not None else "Pending",
                      "Memory": f'{data["rss_bytes"] / 1048576:.1f} MiB' if data["rss_bytes"] is not None else "Pending"}
            rows = "".join(f"<tr><th>{escape(k)}</th><td>{escape(str(v))}</td></tr>" for k, v in fields.items())
            body = ('<!doctype html><html lang="en"><meta charset="utf-8">'
                    '<meta name="viewport" content="width=device-width,initial-scale=1">'
                    '<meta http-equiv="refresh" content="2"><title>hermes on herdr</title>'
                    '<style>body{font:16px system-ui;margin:3rem auto;padding:0 1rem;max-width:44rem;'
                    'background:#f3f5ef;color:#233d36}table{width:100%;border-collapse:collapse}'
                    'th,td{text-align:left;padding:.7rem;border-bottom:1px solid #ccd6cc}'
                    'small,p{color:#425c50}a{color:#226448}</style>'
                    f'<h1>hermes on herdr <small>v{__version__}</small></h1><table>{rows}</table>'
                    '<p>Read-only status · refreshes every 2 seconds · <a href="/health">Health JSON</a></p></html>')
        encoded = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(encoded)

    do_HEAD = do_GET


def serve(config, port):
    with DashboardServer(config, port) as server:
        stopped = threading.Event()

        def sampling():
            while not stopped.is_set():
                server.sample()
                stopped.wait(2)

        worker = threading.Thread(target=sampling, daemon=True, name="http-profile-monitor")
        worker.start()
        print(json.dumps({"schema": 1, "state": "LISTENING", "profile": config.profile_id,
                          "url": server.url + "/", "health_url": server.url + "/health"}), flush=True)
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
        finally:
            stopped.set()
            worker.join(timeout=0.3)
    return 0
