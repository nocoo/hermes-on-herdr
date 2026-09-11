import unittest

from hermes_gateway_herdr.lifecycle import Limits, effective_budget, exit_action, retry_budget
from hermes_gateway_herdr.state import Store
from helpers import Fixture


class LifecycleTests(unittest.TestCase):
    def test_exit_policy_respects_pause_and_newer_intent(self):
        running = {"desired": "running", "revision": 4}
        for code, action in ((75, "retry"), (1, "retry"), (-9, "retry"), (-15, "retry"),
                             (0, "pause"), (2, "fuse"), (78, "fuse"), (42, "fuse")):
            with self.subTest(code=code):
                self.assertEqual(action, exit_action(code, running, 4))
                self.assertEqual("stop", exit_action(code, dict(running, desired="paused"), 4))
        self.assertEqual("retry", exit_action(0, dict(running, revision=5), 4))

    def test_backoff_persists_and_resume_reset_is_one_intent_write(self):
        fixture = Fixture()
        self.addCleanup(fixture.close)
        with Store.initialize(fixture.config.state_dir, fixture.config.binding("fixture")) as store:
            with store.mutation():
                intent = store.set_intent("resume", request_id="original")
                budget = effective_budget(intent, None)
                delays = []
                for index in range(6):
                    budget, delay = retry_budget(budget, 1, 100 + index, Limits())
                    delays.append(delay)
                store.write("fuse.json", budget)
            self.assertEqual([1, 2, 4, 8, 16, 30], delays)
        with Store(fixture.config.state_dir) as store:
            persisted = effective_budget(store.intent(), store.read("fuse.json"))
            self.assertTrue(persisted["fused"])
            self.assertEqual("CRASH_LOOP", persisted["reason"])
            with store.mutation():
                store.set_intent("pause")
                store.set_intent("resume", request_id="original")
                self.assertEqual("paused", store.intent()["desired"])
                self.assertTrue(effective_budget(store.intent(), store.read("fuse.json"))["fused"])
                resumed = store.set_intent("resume")
            self.assertFalse(effective_budget(resumed, store.read("fuse.json"))["fused"])

    def test_restart_storm_rollback_and_jitter_caps(self):
        budget = None
        for now in (100, 101, 102, 50, 51):
            budget, delay = retry_budget(budget, 75, now, Limits())
            self.assertEqual(1, delay)
        self.assertTrue(budget["fused"])
        self.assertEqual("RESTART_STORM", budget["reason"])
        self.assertTrue(retry_budget(budget, 75, 10000, Limits())[0]["fused"])
        self.assertEqual(1.2, retry_budget(None, 1, 1, Limits(), jitter=999)[1])
        self.assertEqual(0.8, retry_budget(None, 1, 1, Limits(), jitter=-999)[1])

