import importlib.util
from pathlib import Path
import unittest

source = Path(__file__).parent / 'live-session/container_test_support.py'
spec = importlib.util.spec_from_file_location('container_test_support', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ContainerFilesystemTests(unittest.TestCase):
    def test_fuse_simulation_is_container_only(self):
        self.assertEqual(module.simulated_live_fstype(
            'fuse.fuse-overlayfs\n', podman_container=True), 'overlay\n')
        with self.assertRaisesRegex(RuntimeError, 'Podman container required'):
            module.simulated_live_fstype('fuse.fuse-overlayfs', podman_container=False)

    def test_native_test_filesystems_unchanged(self):
        for fs in ('overlay', 'tmpfs'):
            self.assertEqual(module.simulated_live_fstype(
                fs, podman_container=True), fs + '\n')

    def test_disk_and_unknown_filesystems_rejected_even_in_container(self):
        for fs in ('ext4', 'btrfs', 'xfs', 'erofs', 'fuse.sshfs', ''):
            with self.subTest(fs=fs), self.assertRaisesRegex(RuntimeError, 'account-test root'):
                module.simulated_live_fstype(fs, podman_container=True)
