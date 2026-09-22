import json
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

    def test_gateway_argv_forces_plugin_owned_named_profile(self):
        self.assertEqual(
            [str(self.config.hermes_bin), "-p", self.config.profile_id, "gateway", "run",
             "--external-supervisor", "--force"],
            self.config.gateway_argv(),
        )

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
        self.assertNotIn("HERMES_ENABLE_PROJECT_PLUGINS", env)
        for value in ("0", "1"):
            self.assertEqual(value, self.config.child_env(dict(source, HERMES_ENABLE_PROJECT_PLUGINS=value))[
                "HERMES_ENABLE_PROJECT_PLUGINS"])

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

    def test_launch_environment_overrides_fail_without_secret_output(self):
        for line in ("HERDR_SOCKET_PATH=/wrong", "GATEWAY_MULTIPLEX_PROFILES=1", "HERMES_HOME=/wrong",
                     "HERMES_GATEWAY_LOCK_DIR=/wrong", "INVOCATION_ID=another-supervisor",
                     "HERMES_GATEWAY_EXTERNAL_SUPERVISOR=0"):
            private_file(self.fixture.profile / ".env", line + "\nTOKEN=fixture-private-sentinel\n")
            with self.assertRaises(GatewayError) as error:
                profile_preflight(self.config)
            self.assertNotIn("fixture-private-sentinel", str(error.exception))

    def test_dotenv_key_syntax_cannot_override_control_context(self):
        for line in ("'HERMES_HOME'=/wrong", "export 'HERDR_SOCKET_PATH'=/wrong", "\t'HGH_GENERATION' = wrong",
                     "\ufeffHERDR_SOCKET_PATH=/wrong",
                     "TOKEN=fixture-private-sentinel\rHERDR_SOCKET_PATH=/wrong"):
            with self.subTest(line=line):
                path = self.fixture.profile / ".env"
                raw = line + "\nTOKEN=fixture-private-sentinel\n"
                private_file(path, raw)
                with self.assertRaises(GatewayError) as error:
                    profile_preflight(self.config)
                self.assertEqual("CONFIG_ERROR", error.exception.code)
                self.assertNotIn("fixture-private-sentinel", str(error.exception))
                self.assertEqual(raw.encode(), path.read_bytes())

    def test_quoted_secret_reference_remains_supported_without_loading_it(self):
        self.fixture.profile_data["model"]["api_key"] = "${HERMES_CUSTOM_TEST_API_KEY}"
        self.fixture.write_profile()
        path = self.fixture.profile / ".env"
        raw = "\ufeffexport 'HERMES_CUSTOM_TEST_API_KEY'='fixture-private-sentinel'\r\n"
        private_file(path, raw)
        profile_preflight(self.config)
        self.assertEqual(raw.encode(), path.read_bytes())

    def test_invalid_config_fields_cannot_change_the_binding(self):
        path = self.fixture.config_dir / "config.json"
        original = json.loads(path.read_text())
        for fields in ({"schema": True}, {"unrecognized": "fixture-private-sentinel"},
                       {"profile_id": "default"}, {"owner_session": "bad\nidentity"},
                       {"expected_platforms": ["telegram", "telegram"]}, {"expected_platforms": [[]]},
                       {"owner_socket": "relative.sock"}, {"profile_home": []}):
            with self.subTest(fields=fields):
                raw = json.dumps(dict(original, **fields))
                private_file(path, raw)
                with self.assertRaises(GatewayError) as error:
                    Config.load(path)
                self.assertEqual("CONFIG_ERROR", error.exception.code)
                self.assertEqual(raw, path.read_text())
                self.assertNotIn("fixture-private-sentinel", str(error.exception))
        self.assertFalse(self.config.state_dir.exists())

    def test_ambient_focus_cannot_change_owner_binding(self):
        other = dict(self.fixture.context(), HERDR_SOCKET_PATH=str(self.fixture.root / "other.sock"))
        with self.assertRaises(GatewayError) as error:
            self.config.check_context(other)
        self.assertEqual("NOT_OWNER", error.exception.code)

    def test_hermes_configuration_and_toolsets_are_not_plugin_policy(self):
        self.fixture.profile_data = {
            "model": {"provider": "auto", "api_key": "fixture-private-sentinel"},
            "terminal": {"backend": "docker"}, "gateway": {"multiplex_profiles": True},
            "nous": {"keepalive_interval_seconds": 900},
            "platform_toolsets": {"discord": ["terminal", "skills", "memory", "connections", "future-toolset"]},
            "agent": {"disabled_toolsets": []}, "plugins": {"enabled": ["custom"]},
            "mcp_servers": {"custom": {}}, "hooks": ["custom"]}
        self.fixture.write_profile()
        private_file(self.fixture.profile / ".env", "HERMES_YOLO_MODE=1\nTELEGRAM_ALLOW_ALL_USERS=1\n"
                     "HERMES_ENABLE_PROJECT_PLUGINS=1\nHERMES_CUSTOM_TEST_API_KEY=fixture-private-sentinel\n")
        paths = (self.fixture.profile / "config.yaml", self.fixture.profile / ".env")
        before = [path.read_bytes() for path in paths]
        profile_preflight(self.config)
        self.assertEqual(before, [path.read_bytes() for path in paths])
        self.assertEqual("0", self.config.child_env(self.fixture.context())["GATEWAY_MULTIPLEX_PROFILES"])

    def test_hermes_owns_yaml_parsing_and_optional_profile_files(self):
        path = self.fixture.profile / "config.yaml"
        private_file(path, "model: [broken")
        profile_preflight(self.config)
        self.assertEqual("model: [broken", path.read_text())
        path.unlink()
        (self.fixture.profile / ".env").unlink()
        profile_preflight(self.config)
