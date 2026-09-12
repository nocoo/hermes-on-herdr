import copy
from contextlib import chdir
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

    def test_model_key_can_reference_a_profile_environment_secret_without_resolving_it(self):
        self.fixture.profile_data["model"]["api_key"] = "${HERMES_CUSTOM_TEST_API_KEY}"
        self.fixture.write_profile()
        private_file(self.fixture.profile / ".env", "HERMES_CUSTOM_TEST_API_KEY=fixture-private-sentinel\n")
        before = {name: (self.fixture.profile / name).read_bytes() for name in ("config.yaml", ".env")}
        profile_preflight(self.config)
        self.assertEqual(before, {name: (self.fixture.profile / name).read_bytes() for name in before})

    def test_model_key_rejects_inline_secrets_and_nonliteral_environment_references(self):
        for value in ("fixture-private-sentinel", "${KEY}suffix", "${KEY:-fallback}", "$(command)", None, []):
            with self.subTest(value=value):
                self.fixture.profile_data["model"]["api_key"] = value
                self.fixture.write_profile()
                with self.assertRaises(GatewayError) as error:
                    profile_preflight(self.config)
                self.assertNotIn("fixture-private-sentinel", str(error.exception))

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

    def test_dotenv_key_syntax_cannot_override_control_context(self):
        # Hermes' pinned python-dotenv accepts quoted keys; its loader strips a UTF-8 BOM.
        for line in ("'HERMES_HOME'=/wrong", "export 'HERDR_SOCKET_PATH'=/wrong", "\t'HGH_GENERATION' = wrong",
                     "'TELEGRAM_ALLOW_ALL_USERS'=1", "\ufeffHERDR_SOCKET_PATH=/wrong",
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

    def test_deep_yaml_is_a_sanitized_configuration_error(self):
        path = self.fixture.profile / "config.yaml"
        raw = "nested: " + "[" * 1500 + "fixture-private-sentinel" + "]" * 1500
        private_file(path, raw)
        with self.assertRaises(GatewayError) as error:
            profile_preflight(self.config)
        self.assertEqual("CONFIG_ERROR", error.exception.code)
        self.assertNotIn("fixture-private-sentinel", str(error.exception))
        self.assertEqual(raw, path.read_text())

    def test_malformed_policy_sections_fail_closed(self):
        original = copy.deepcopy(self.fixture.profile_data)
        for key in ("model", "terminal", "plugins", "gateway", "nous", "platform_toolsets", "agent"):
            for value in (None, [], "fixture-private-sentinel"):
                with self.subTest(key=key, value=value):
                    self.fixture.profile_data = dict(original, **{key: value})
                    self.fixture.write_profile()
                    with self.assertRaises(GatewayError) as error:
                        profile_preflight(self.config)
                    self.assertEqual("CONFIG_ERROR", error.exception.code)
                    self.assertNotIn("fixture-private-sentinel", str(error.exception))

    def test_terminal_cwd_cannot_borrow_the_callers_working_directory(self):
        terminal = dict(self.fixture.profile_data["terminal"])
        terminal.pop("cwd")
        with chdir(self.config.agent_cwd):
            for fields in ({}, {"cwd": None}, {"cwd": ""}, {"cwd": "."}):
                with self.subTest(fields=fields):
                    self.fixture.profile_data["terminal"] = dict(terminal, **fields)
                    self.fixture.write_profile()
                    with self.assertRaises(GatewayError) as error:
                        profile_preflight(self.config)
                    self.assertEqual("CONFIG_ERROR", error.exception.code)

    def test_model_urls_reject_credentials_without_printing_them(self):
        for field in ("base_url", "api_base"):
            for url in ("https://user:fixture-private-sentinel@example.invalid/v1",
                        "https://example.invalid/v1?API_KEY=fixture-private-sentinel"):
                with self.subTest(field=field, url=url):
                    self.fixture.profile_data["model"] = {"provider": "fixture", "default": "model", field: url}
                    self.fixture.write_profile()
                    with self.assertRaises(GatewayError) as error:
                        profile_preflight(self.config)
                    self.assertNotIn("fixture-private-sentinel", str(error.exception))
        self.fixture.profile_data["model"]["api_base"] = "https://example.invalid/v1?region=test"
        self.fixture.write_profile()
        profile_preflight(self.config)

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
