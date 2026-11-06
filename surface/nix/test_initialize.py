import unittest
import stat
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from initialize import backing_mapping_present, preflight, image_owned


class InitializeTests(unittest.TestCase):
    def test_image_marker_is_root_owned_regular_and_known_schema(self):
        resources = MagicMock()
        marker = resources.__truediv__.return_value
        marker.exists.return_value = True
        marker.lstat.return_value = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0)
        marker.read_text.return_value = '{"schema": 1}'
        with patch('initialize.RESOURCES', resources):
            self.assertTrue(image_owned())
            marker.read_text.return_value = '{"schema": 2}'
            self.assertFalse(image_owned())
            for mode, uid in ((stat.S_IFREG | 0o666, 0), (stat.S_IFLNK | 0o777, 0), (stat.S_IFREG | 0o644, 1000)):
                marker.lstat.return_value = SimpleNamespace(st_mode=mode, st_uid=uid)
                with self.assertRaises(RuntimeError):
                    image_owned()

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
