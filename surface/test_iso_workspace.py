from pathlib import Path
import tempfile
import unittest
from iso_workspace import MARKER, TOKEN, remove


class IsoWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'work'
        self.root.mkdir()
        (self.root / MARKER).write_text(TOKEN)
        self.mounts = Path(self.temp.name) / 'mountinfo'
        self.mounts.write_text('')

    def test_removes_only_intermediates_keeps_iso_and_log(self):
        (self.root / 'live-oci').mkdir()
        (self.root / 'live-oci/blob').write_text('data')
        (self.root / 'surface.iso').write_text('old')
        for name in ('azurefin-aarch64.iso', 'audit.log'):
            (self.root / name).write_text('keep')
        remove(self.root, ['live-oci', 'surface.iso'], self.mounts)
        self.assertFalse((self.root / 'live-oci').exists())
        self.assertFalse((self.root / 'surface.iso').exists())
        self.assertEqual((self.root / 'azurefin-aarch64.iso').read_text(), 'keep')
        self.assertEqual((self.root / 'audit.log').read_text(), 'keep')

    def test_invalid_targets_refuse_entire_request(self):
        (self.root / 'live-oci').mkdir()
        for name in ('..', '/', 'azurefin-aarch64.iso', 'seed/../outside', 'unknown'):
            with self.assertRaises(ValueError):
                remove(self.root, ['live-oci', name], self.mounts)
            self.assertTrue((self.root / 'live-oci').exists())

    def test_refuses_unmarked_workspace(self):
        (self.root / MARKER).write_text('wrong')
        with self.assertRaises(ValueError):
            remove(self.root, ['live-oci'], self.mounts)

    def test_refuses_links_and_preserves_external_files(self):
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        (outside / 'file').write_text('keep')
        (self.root / 'live-oci').symlink_to(outside)
        with self.assertRaises(ValueError):
            remove(self.root, ['live-oci'], self.mounts)
        self.assertEqual((outside / 'file').read_text(), 'keep')

    def test_refuses_nested_mount_before_any_deletion(self):
        for name in ('live-oci', 'audit'):
            (self.root / name).mkdir()
        self.mounts.write_text(f'1 0 7:0 / {self.root}/audit/iso ro - iso9660 /dev/loop0 ro\n')
        with self.assertRaises(ValueError):
            remove(self.root, ['live-oci', 'audit'], self.mounts)
        self.assertTrue((self.root / 'live-oci').exists())

    def test_nested_symlink_is_not_followed(self):
        outside = Path(self.temp.name) / 'keep'
        outside.write_text('keep')
        (self.root / 'live-oci').mkdir()
        (self.root / 'live-oci/link').symlink_to(outside)
        remove(self.root, ['live-oci'], self.mounts)
        self.assertEqual(outside.read_text(), 'keep')


if __name__ == '__main__':
    unittest.main()
