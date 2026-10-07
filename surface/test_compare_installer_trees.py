import os
from pathlib import Path
import shutil
import tempfile
import unittest

from compare_installer_trees import compare


class TreeComparisonTests(unittest.TestCase):
    def test_contents_metadata_links_and_xattrs(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a", Path(directory) / "b"
            a.mkdir()
            (a / "file").write_bytes(b"original")
            os.setxattr(a / "file", "user.test", b"value")
            os.link(a / "file", a / "hardlink")
            (a / "symlink").symlink_to("file")
            shutil.copytree(a, b, symlinks=True)
            (b / "hardlink").unlink()
            os.link(b / "file", b / "hardlink")
            shutil.copystat(a, b)
            compare(a, b)
            stamp = (b / "file").stat()
            (b / "file").write_bytes(b"modified")
            os.utime(b / "file", ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            with self.assertRaisesRegex(ValueError, "contents mismatch"):
                compare(a, b)
            (b / "file").write_bytes(b"original")
            os.utime(b / "file", ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            os.setxattr(b / "file", "user.test", b"changed")
            with self.assertRaisesRegex(ValueError, "attribute mismatch"):
                compare(a, b)
