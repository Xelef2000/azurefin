"""Local-only tests: no host accounts, services or disks are modified."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

SOURCE = Path(__file__).parent / 'live-session/setup.py'
spec = importlib.util.spec_from_file_location('live_user', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LiveUserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'proc').mkdir()
        (self.root / 'etc').mkdir()
        (self.root / 'proc/cmdline').write_text('quiet azurefin.live=1')
        (self.root / 'etc/passwd').write_text('root:x:0:0:root:/root:/bin/bash\n')
        self.mock = patch.object(module, 'run', return_value=SimpleNamespace(stdout='overlay\n'))
        self.run = self.mock.start()
        self.addCleanup(self.mock.stop)

    def test_live_account_configuration(self):
        module.configure(self.root)
        self.run.assert_any_call('passwd', '--delete', 'liveuser')
        self.run.assert_any_call('systemctl', 'mask', '--runtime', '--now', 'sshd.service', 'sshd.socket')
        sudoers = self.root / 'etc/sudoers.d/90-azurefin-live'
        self.assertEqual(sudoers.stat().st_mode & 0o777, 0o440)
        self.assertEqual(sudoers.read_text(), 'liveuser ALL=(ALL) NOPASSWD: ALL\n')
        config = (self.root / 'etc/gdm/custom.conf').read_text()
        self.assertIn('AutomaticLogin = liveuser', config)
        self.assertIn('InitialSetupEnable = False', config)

    def test_normal_boot_untouched(self):
        (self.root / 'proc/cmdline').write_text('quiet')
        with self.assertRaisesRegex(RuntimeError, 'Not an Azurefin live boot'):
            module.configure(self.root)
        self.run.assert_not_called()

    def test_installed_root_rejected(self):
        for fs in ('ext4', 'btrfs', 'xfs', 'erofs', 'fuse.fuse-overlayfs'):
            self.run.return_value.stdout = fs
            with self.assertRaisesRegex(RuntimeError, 'non-ephemeral'):
                module.configure(self.root)
        self.assertFalse((self.root / 'etc/sudoers.d').exists())
        self.assertFalse(any(call.args[0] == 'useradd' for call in self.run.call_args_list))

    def test_existing_user_not_unlocked(self):
        (self.root / 'etc/passwd').write_text('liveuser:x:1000:1000::/home/liveuser:/bin/bash\n')
        with self.assertRaisesRegex(RuntimeError, 'existing liveuser'):
            module.configure(self.root)
        self.assertEqual(self.run.call_count, 1)

    def test_ssh_failure_prevents_account_creation(self):
        def command(*args):
            if args[0] == 'systemctl':
                raise RuntimeError('SSH masking failed')
            return SimpleNamespace(stdout='overlay\n')
        self.run.side_effect = command
        with self.assertRaisesRegex(RuntimeError, 'SSH masking failed'):
            module.configure(self.root)
        self.assertFalse(any(call.args[0] == 'useradd' for call in self.run.call_args_list))

    def test_gdm_requires_setup_and_setup_fails_without_flag(self):
        directory = SOURCE.parent
        self.assertIn('Requires=azurefin-live-user.service', (directory / 'gdm-live-user.conf').read_text())
        unit = (directory / 'azurefin-live-user.service').read_text()
        self.assertIn('AssertKernelCommandLine=azurefin.live=1', unit)
        self.assertIn('Before=gdm.service', unit)


if __name__ == '__main__':
    unittest.main()
