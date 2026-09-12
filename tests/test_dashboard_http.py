from dataclasses import replace
from http.client import HTTPConnection
import json
import threading
import time
import unittest
from unittest.mock import patch

from hermes_gateway_herdr.dashboard_http import DashboardServer
from hermes_gateway_herdr.monitor import Profile, Snapshot
from helpers import Fixture


class HttpDashboardTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
        self.server = DashboardServer(self.fixture.config, 0)
        self.addCleanup(self.server.server_close)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.profile = Profile(self.fixture.config.profile_id, self.fixture.profile, managed=True, state="READY",
                               pid=123, supervision="external", platforms=(("telegram", "connected"),), pane="w1:p2")
        self.publish(self.profile)

    def stop(self):
        self.server.shutdown()
        self.thread.join(timeout=1)

    def publish(self, profile, *, age=0, error=""):
        self.server.latest = (Snapshot((profile,), time.time(), error=error), time.monotonic() - age)

    def request(self, path="/health", *, method="GET", headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read().decode()
        finally:
            connection.close()

    def test_page_and_health_read_the_same_sample_without_polling_on_requests(self):
        self.assertEqual("127.0.0.1", self.server.server_address[0])
        with patch.object(self.server.monitor, "collect", side_effect=AssertionError("request initiated sampling")):
            for _ in range(3):
                status, headers, body = self.request()
                self.assertEqual(200, status)
                self.assertEqual("no-store", headers["Cache-Control"])
                health = json.loads(body)
                self.assertTrue(health["healthy"])
                self.assertEqual(self.profile.name, health["profile"])
                self.assertEqual(123, health["gateway_pid"])
            status, _, page = self.request("/")
            self.assertEqual(200, status)
            self.assertIn(self.profile.name, page)
            self.assertIn('href="/health"', page)
            self.assertNotIn(str(self.fixture.profile), page)

    def test_missing_ownership_platform_errors_and_stale_samples_never_report_healthy(self):
        for change in ({"state": "DEGRADED"}, {"pid": None}, {"pane": ""}, {"managed": False},
                       {"name": "other"}, {"error": "OWNER_UNAVAILABLE"}, {"platforms": ()},
                       {"platforms": (("telegram", "disconnected"),)}):
            with self.subTest(change=change):
                self.publish(replace(self.profile, **change))
                status, _, body = self.request()
                self.assertEqual(503, status)
                self.assertFalse(json.loads(body)["healthy"])
        self.publish(self.profile, age=100)
        status, _, body = self.request()
        self.assertEqual(503, status)
        self.assertEqual("STALE_SAMPLE", json.loads(body)["error"])
        with patch.object(self.server.monitor, "collect", side_effect=RuntimeError("fixture-secret")):
            self.server.sample()
        status, _, body = self.request()
        self.assertEqual(503, status)
        self.assertEqual("COLLECTOR_UNAVAILABLE", json.loads(body)["error"])
        self.assertNotIn("fixture-secret", body)

    def test_foreign_browser_origins_hosts_and_mutations_are_rejected(self):
        self.assertEqual(403, self.request(headers={"Host": "untrusted.example"})[0])
        self.assertEqual(403, self.request(headers={"Origin": "https://untrusted.example"})[0])
        self.assertEqual(501, self.request(method="POST")[0])
        self.assertEqual(404, self.request("/config.json")[0])
        self.assertEqual(200, self.request(method="HEAD")[0])
