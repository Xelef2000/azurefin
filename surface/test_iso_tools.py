import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class IsoToolTests(unittest.TestCase):
    def run_check(self, missing=None):
        with tempfile.TemporaryDirectory() as temp:
            for name in ('podman python3 xorriso mcopy grub2-script-check implantisomd5 '
                         'checkisomd5 unsquashfs lsinitrd mount umount unshare find od '
                         'sha256sum split').split():
                if name != missing:
                    (Path(temp) / name).symlink_to('/bin/true')
            return subprocess.run(
                ['/bin/bash', str(Path(__file__).with_name('52-check-iso-tools.sh'))],
                env=dict(os.environ, PATH=temp), capture_output=True, text=True)

    def test_complete_toolset(self):
        self.assertEqual(self.run_check().returncode, 0)

    def test_missing_grub_checker_is_named(self):
        result = self.run_check('grub2-script-check')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Missing ISO build prerequisite: grub2-script-check', result.stderr)


if __name__ == '__main__':
    unittest.main()
