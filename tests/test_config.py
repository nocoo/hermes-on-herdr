from dataclasses import replace
import json
from pathlib import Path
import unittest

from hermes_gateway_herdr.config import Config, PANE_KEYS, profile_preflight
from hermes_gateway_herdr.errors import GatewayError
from helpers import Fixture, private_file


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
        self.config = self.fixture.config

    def test_config_round_trip_preserves_venv_interpreter_spelling(self):
        loaded = Config.load(self.fixture.config_dir / "config.json")
        self.assertEqual(self.config, loaded)
        self.assertEqual(str(self.config.python_bin), str(loaded.python_bin))
        profile_preflight(loaded)

    def test_child_environment_keeps_pane_ids_and_strips_unrelated_credentials(self):
        source = dict(self.fixture.context(), OPENAI_API_KEY="fixture-do-not-copy", ARBITRARY_SECRET="sentinel",
                      PYTHONPATH="/bad", BASH_ENV="/bad", INVOCATION_ID="service", HERMES_YOLO_MODE="1",
                      PATH="/untrusted", HERMES_HOME="/other-profile")
        env = self.config.child_env(source)
        self.assertEqual({key: source[key] for key in PANE_KEYS}, {key: env[key] for key in PANE_KEYS})
        self.assertFalse(set(env) & {"OPENAI_API_KEY", "ARBITRARY_SECRET", "PYTHONPATH", "BASH_ENV",
                                     "INVOCATION_ID", "HERMES_YOLO_MODE"})
        self.assertEqual(str(self.config.profile_home), env["HERMES_HOME"])
        self.assertNotIn("/untrusted", env["PATH"])
        self.assertEqual("0", env["GATEWAY_MULTIPLEX_PROFILES"])

    def test_missing_profile_or_mismatched_runtime_does_not_create_it(self):
        raw = json.loads((self.fixture.config_dir / "config.json").read_text())
        missing = self.fixture.root / "missing"
        raw["profile_home"] = str(missing)
        private_file(self.fixture.config_dir / "config.json", json.dumps(raw))
        with self.assertRaises(GatewayError):
            Config.load(self.fixture.config_dir / "config.json")
        self.assertFalse(missing.exists())
        self.fixture.write_config()
        private_file(self.fixture.config_dir / "runtime-python", "/some/other/python\n")
        with self.assertRaises(GatewayError):
            Config.load(self.fixture.config_dir / "config.json")

    def test_static_model_still_requires_disabling_nous_keepalive(self):
        for setting in (None, 900, False):
            with self.subTest(setting=setting):
                self.fixture.profile_data["nous"]["keepalive_interval_seconds"] = setting
                self.fixture.write_profile()
                with self.assertRaises(GatewayError):
                    profile_preflight(self.config)

    def test_env_overrides_and_duplicate_yaml_fail_closed_without_secret_output(self):
        for line in ("HERDR_SOCKET_PATH=/wrong", "GATEWAY_MULTIPLEX_PROFILES=1", "HERMES_HOME=/wrong"):
            private_file(self.fixture.profile / ".env", line + "\nTOKEN=fixture-private-sentinel\n")
            with self.assertRaises(GatewayError) as error:
                profile_preflight(self.config)
            self.assertNotIn("fixture-private-sentinel", str(error.exception))
        private_file(self.fixture.profile / ".env", "")
        private_file(self.fixture.profile / "config.yaml", "model: {}\nmodel: {}\n")
        with self.assertRaises(GatewayError):
            profile_preflight(self.config)

    def test_ambient_focus_cannot_change_owner_binding(self):
        other = dict(self.fixture.context(), HERDR_SOCKET_PATH=str(self.fixture.root / "other.sock"))
        with self.assertRaises(GatewayError) as error:
            self.config.check_context(other)
        self.assertEqual("NOT_OWNER", error.exception.code)

    def test_multiplex_or_unreviewed_tools_are_rejected(self):
        self.fixture.profile_data["multiplex_profiles"] = True
        self.fixture.write_profile()
        with self.assertRaises(GatewayError):
            profile_preflight(self.config)
        self.fixture.profile_data.pop("multiplex_profiles")
        self.fixture.profile_data["platform_toolsets"]["telegram"].append("browser")
        self.fixture.write_profile()
        with self.assertRaises(GatewayError):
            profile_preflight(self.config)
