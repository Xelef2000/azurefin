import stat
import unittest
from unittest.mock import MagicMock, patch

from directory import prepare


class DirectoryTests(unittest.TestCase):
    def paths(self, mode=0o755, uid=0, gid=0):
        parent, mount = MagicMock(), MagicMock()
        for path in (parent, mount):
            path.lstat.return_value = type('Info', (), {
                'st_mode': stat.S_IFDIR | 0o755, 'st_uid': 0})()
        backing = parent.__truediv__.return_value
        backing.lstat.return_value = type('Info', (), {
            'st_mode': stat.S_IFDIR | mode, 'st_uid': uid, 'st_gid': gid})()
        return parent, mount, backing

    def test_create(self):
        parent, mount, backing = self.paths()
        prepare(parent, mount)
        backing.mkdir.assert_called_once_with(mode=0o755)
        backing.chmod.assert_not_called()

    def test_preserve_existing_directory(self):
        parent, mount, backing = self.paths()
        backing.mkdir.side_effect = FileExistsError
        prepare(parent, mount)
        backing.chmod.assert_not_called()

    def test_reject_unsafe_existing_directory_without_chmod(self):
        for mode, uid, gid in ((0o777, 0, 0), (0o700, 0, 0), (0o755, 1000, 0), (0o755, 0, 1000)):
            with self.subTest(mode=mode, uid=uid, gid=gid):
                parent, mount, backing = self.paths(mode, uid, gid)
                backing.mkdir.side_effect = FileExistsError
                with self.assertRaises(RuntimeError):
                    prepare(parent, mount)
                backing.chmod.assert_not_called()

    def test_reject_symlink_parent_before_creation(self):
        parent, mount, backing = self.paths()
        parent.lstat.return_value.st_mode = stat.S_IFLNK | 0o777
        with self.assertRaises(RuntimeError):
            prepare(parent, mount)
        backing.mkdir.assert_not_called()

    def test_reject_symlink_backing(self):
        parent, mount, backing = self.paths()
        backing.mkdir.side_effect = FileExistsError
        backing.lstat.return_value.st_mode = stat.S_IFLNK | 0o777
        with self.assertRaises(RuntimeError):
            prepare(parent, mount)

    def test_foreign_mountpoint_contents_not_hidden(self):
        parent, mount, backing = self.paths()
        mount.iterdir.return_value = iter(['existing-store'])
        backing.exists.return_value = False
        with self.assertRaisesRegex(RuntimeError, 'refusing to hide'):
            prepare(parent, mount)
        backing.mkdir.assert_not_called()

    def test_other_backing_does_not_authorize_hiding_contents(self):
        parent, mount, backing = self.paths()
        mount.iterdir.return_value = iter(['existing-store'])
        backing.exists.return_value = True
        with patch('directory.os.path.samefile', return_value=False), self.assertRaises(RuntimeError):
            prepare(parent, mount)
        backing.mkdir.assert_not_called()

    def test_existing_correct_bind_mount_allowed(self):
        parent, mount, backing = self.paths()
        mount.iterdir.return_value = iter(['owned-store'])
        backing.exists.return_value = True
        backing.mkdir.side_effect = FileExistsError
        with patch('directory.os.path.samefile', return_value=True):
            prepare(parent, mount)
        backing.chmod.assert_not_called()


if __name__ == '__main__':
    unittest.main()
