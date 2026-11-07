import copy
import errno
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lifecycle import classify, digest, locked, read_state, receipt_matches, seed_config_file, write_state
from adapt_plan import adapt
from test_plan import fixture


def state(phase="prepared"):
    return {"schema": 1, "installer_sha256": "a" * 64,
            "plan_sha256": digest(adapt(fixture())), "phase": phase}


def classify_state(metadata, empty=True, conflict=False, payload="a" * 64):
    return classify(metadata, store_empty=empty, accounts_conflict=conflict,
                    payload_sha256=payload)


def interrupted_writer(directory):
    with locked(directory):
        write_state(directory, state("installing"))
        os._exit(17)


class LifecycleTests(unittest.TestCase):
    def test_process_exit_releases_lock_and_retains_partial_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            child = multiprocessing.Process(target=interrupted_writer, args=(directory,))
            child.start()
            child.join(timeout=10)
            if child.is_alive():
                child.terminate()
                child.join()
                self.fail("Checkpoint test process stalled")
            self.assertEqual(child.exitcode, 17)
            with locked(directory):
                self.assertEqual(classify_state(read_state(directory)), "needs-reconciliation")

    def test_config_seed_preserves_admin_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nix.conf"
            seed_config_file(target, b"defaults\n")
            self.assertEqual(target.read_bytes(), b"defaults\n")
            target.write_bytes(b"admin changes\n")
            seed_config_file(target, b"new defaults\n")
            self.assertEqual(target.read_bytes(), b"admin changes\n")

    def test_failed_config_write_does_not_publish_partial_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nix.conf"
            with patch("lifecycle.os.fsync", side_effect=OSError(errno.ENOSPC, "full")):
                with self.assertRaises(OSError):
                    seed_config_file(target, b"defaults\n")
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_config_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nix.conf"
            target.symlink_to(Path(directory) / "elsewhere")
            with self.assertRaises(ValueError):
                seed_config_file(target, b"defaults\n")

    def test_unowned_store_or_accounts_are_foreign(self):
        self.assertEqual(classify_state(None), "fresh")
        self.assertEqual(classify_state(None, empty=False), "foreign")
        self.assertEqual(classify_state(None, conflict=True), "foreign")

    def test_prepared_can_start_only_when_untouched(self):
        self.assertEqual(classify_state(state()), "start")
        self.assertEqual(classify_state(state(), empty=False), "needs-reconciliation")
        self.assertEqual(classify_state(state(), conflict=True), "needs-reconciliation")

    def test_killed_install_is_never_blindly_replayed(self):
        for empty in (True, False):
            self.assertEqual(classify_state(state("installing"), empty), "needs-reconciliation")

    def test_completed_runtime_not_reinstalled_for_new_payload(self):
        self.assertEqual(classify_state(state("complete"), payload="b" * 64), "validate")
        self.assertEqual(classify_state(state("installing"), payload="b" * 64),
                         "needs-original-payload")

    def test_unknown_metadata_refused(self):
        for changed in ({"schema": 2}, {"phase": "ready"}, {"plan_sha256": "bad"}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                classify_state(state() | changed)

    def test_receipt_cannot_change_action_arguments(self):
        plan = adapt(fixture())
        receipt = copy.deepcopy(plan)
        receipt["actions"][0]["state"] = "Progress"
        self.assertTrue(receipt_matches(plan, receipt))
        receipt["actions"][-1]["action"]["path"] = "/nix"
        self.assertFalse(receipt_matches(plan, receipt))

    def test_receipt_unknown_state_refused(self):
        plan = adapt(fixture())
        receipt = copy.deepcopy(plan)
        receipt["actions"][0]["state"] = "Maybe"
        with self.assertRaises(ValueError):
            receipt_matches(plan, receipt)

    def test_atomic_roundtrip_and_lock_exclusion(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(read_state(directory))
            with locked(directory):
                with self.assertRaises(BlockingIOError), locked(directory):
                    pass
                write_state(directory, state())
            self.assertEqual(read_state(directory), state())
            self.assertEqual((Path(directory) / "state.json").stat().st_mode & 0o777, 0o600)

    def test_full_disk_keeps_previous_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory, locked(directory):
            write_state(directory, state())
            with patch("lifecycle.os.fsync", side_effect=OSError(errno.ENOSPC, "full")):
                with self.assertRaises(OSError):
                    write_state(directory, state("installing"))
            self.assertEqual(read_state(directory), state())
            self.assertEqual(list(Path(directory).glob(".state-*")), [])

    def test_symlink_state_and_lock_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "state.json").symlink_to(root / "other")
            with self.assertRaises(OSError):
                read_state(directory)
            (root / "lock").symlink_to(root / "other")
            with self.assertRaises(OSError), locked(directory):
                pass


if __name__ == "__main__":
    unittest.main()
