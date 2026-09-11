import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import psutil

from hermes_gateway_herdr.errors import GatewayError
from hermes_gateway_herdr.identity import capture, hermes_start_matches, owner_key, signal_verified


class IdentityTests(unittest.TestCase):
    def test_aliases_share_owner_key_and_pid_is_not_part_of_binding(self):
        with tempfile.TemporaryDirectory() as root:
            profile = Path(root) / "profile"
            profile.mkdir()
            alias = Path(root) / "alias"
            alias.symlink_to(profile, target_is_directory=True)
            self.assertEqual(owner_key(profile, Path(root) / "owner.sock"),
                             owner_key(alias, Path(root) / "owner.sock"))
            self.assertNotEqual(owner_key(profile, Path(root) / "owner.sock"),
                                owner_key(profile, Path(root) / "other.sock"))

    def test_reused_pid_never_receives_signal(self):
        child = subprocess.Popen([sys.executable, "-I", "-B", "-c", "import sys; sys.stdin.read()"],
                                 stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            identity = capture(child.pid)
            stale = dict(identity, start_fingerprint=dict(identity["start_fingerprint"], value="not-this-process"))
            with self.assertRaises(GatewayError) as error:
                signal_verified(stale, signal.SIGTERM)
            self.assertEqual("IDENTITY_CHANGED", error.exception.code)
            self.assertIsNone(child.poll())
            self.assertTrue(signal_verified(identity, signal.SIGTERM))
            child.wait(timeout=10)
            self.assertFalse(signal_verified(identity, signal.SIGTERM))
        finally:
            if child.poll() is None:
                child.terminate()
            child.communicate(timeout=10)

    def test_permission_failure_is_unknown_not_absent(self):
        with patch("hermes_gateway_herdr.identity.psutil.Process", side_effect=psutil.AccessDenied()):
            with self.assertRaises(GatewayError) as error:
                capture(os.getpid())
            self.assertEqual("UNKNOWN", error.exception.code)

    def test_hermes_fingerprint_units_are_explicit(self):
        identity = capture(os.getpid())
        self.assertTrue(hermes_start_matches(identity, int(identity["create_time"] * 100)))
        self.assertFalse(hermes_start_matches(identity, identity["create_time"]))
        self.assertFalse(hermes_start_matches(identity, "2026-09-11T00:00:00Z"))

    def test_permission_race_requires_proof_of_disappearance(self):
        proc = psutil.Process(os.getpid())
        with patch("hermes_gateway_herdr.identity.psutil.Process", return_value=proc), \
                patch.object(proc, "uids", side_effect=psutil.AccessDenied()), \
                patch.object(proc, "is_running", return_value=False):
            self.assertIsNone(capture(os.getpid()))
