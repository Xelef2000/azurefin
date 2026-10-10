import argparse
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import postinstall_firmware as setup


class PostInstallTests(unittest.TestCase):
    def setUp(self):
        old_umask = setup.os.umask(0o022)
        self.addCleanup(setup.os.umask, old_umask)

    def test_address(self):
        self.assertEqual(setup.address('aa:bb:cc:dd:ee:ff'), 'AA:BB:CC:DD:EE:FF')
        for value in ('', '00:00:00:00:00:00', 'FF:FF:FF:FF:FF:FF', 'hello'):
            with self.assertRaises(argparse.ArgumentTypeError):
                setup.address(value)

    def test_payload_requires_success_and_stays_in_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp)
            payload = runs / 'azurefin-provision.ABCD' / 'container'
            payload.mkdir(parents=True)
            with self.assertRaises(FileNotFoundError):
                setup.ready_payload(str(payload), runs)
            (payload.parent / 'READY').write_text(str(payload))
            for name in ('index.json', 'oci-layout'):
                (payload / name).write_text('{}')
            self.assertEqual(setup.ready_payload(str(payload), runs), payload)
            with self.assertRaises(RuntimeError):
                setup.ready_payload('/tmp/untrusted/container', runs)
            link = runs / 'azurefin-provision.LINK'
            link.symlink_to(payload.parent)
            with self.assertRaises(RuntimeError):
                setup.ready_payload(str(link / 'container'), runs)

    def test_failed_preparation_never_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(setup, 'SEED', Path(tmp)), patch.object(setup, 'RUNS', Path(tmp) / 'runs'), \
                 patch('sys.argv', ['azurefin-setup-firmware', '--download']), \
                 patch.object(setup.os, 'geteuid', return_value=0), \
                 patch.object(setup, 'prepare', side_effect=RuntimeError('build failed')), \
                 patch.object(setup.subprocess, 'run') as run:
                with self.assertRaises(RuntimeError):
                    setup.main()
                run.assert_called_once_with(['bootc', 'status'], check=True)

    def test_installer_has_no_preparation_or_workspace(self):
        ks = Path(__file__).with_name('release-installer.ks').read_text()
        self.assertNotIn('%pre ', ks)
        self.assertNotIn('AZUREFIN_WORK', ks)
        self.assertNotIn('clearpart', ks)
        self.assertIn('ostreecontainer --url=/run/install/repo/azurefin/base-oci --transport=oci', ks)
        self.assertIn('/mnt/sysroot/var/lib/azurefin/installer', ks)

    def test_success_stages_local_payload_then_sets_address_without_reboot(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = Path(tmp) / 'private/container'
            with patch.object(setup, 'SEED', Path(tmp)), patch.object(setup, 'RUNS', Path(tmp) / 'runs'), \
                 patch('sys.argv', ['azurefin-setup-firmware', '--download',
                                    '--bluetooth-address', 'aa:bb:cc:dd:ee:ff']), \
                 patch.object(setup.os, 'geteuid', return_value=0), \
                 patch.object(setup, 'prepare', return_value=payload), \
                 patch.object(setup.subprocess, 'run') as run:
                setup.main()
                self.assertEqual([call.args[0] for call in run.call_args_list], [
                    ['bootc', 'status'],
                    ['bootc', 'switch', '--transport', 'oci', str(payload)],
                    ['azurefin-extract-firmware', '--bluetooth-address', 'AA:BB:CC:DD:EE:FF']])

    def test_invalid_base_id_does_not_launch_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed = Path(tmp)
            (seed / 'base-image-id').write_text('latest')
            with patch.object(setup.subprocess, 'Popen') as popen:
                with self.assertRaises(RuntimeError):
                    setup.prepare(seed, seed, None)
                popen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
