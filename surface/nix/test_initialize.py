import unittest
from unittest.mock import patch

from initialize import backing_mapping_present, preflight


class InitializeTests(unittest.TestCase):
    def test_mapping_missing(self):
        self.assertFalse(backing_mapping_present("SELinux Local fcontext Equivalence\n"))

    def test_mapping_exact(self):
        self.assertTrue(backing_mapping_present("header\n/var/lib/nix = /nix\n"))

    def test_conflicting_mapping_refused(self):
        for value in ("/var/lib/nix = /other", "/var/lib/nix/store(/.*)? all files custom_t",
                      "/nix/store(/.*)? all files custom_t"):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                backing_mapping_present(value)

    def test_do_not_touch_host_without_disposable_flag(self):
        with patch.dict("os.environ", {}, clear=True), self.assertRaises(RuntimeError):
            preflight()


if __name__ == '__main__':
    unittest.main()
