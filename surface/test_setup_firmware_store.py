import unittest
from pathlib import Path
from unittest.mock import patch

import setup_firmware_store as setup

UUID = 'a98d77ee-68a7-4863-8fca-843cc4808aba'


class StoreSetupTests(unittest.TestCase):
    def mounts(self):
        return {'filesystems': [{'target': '/boot', 'fstype': 'ext4',
                                 'uuid': UUID, 'options': 'rw,nodev'}]}

    def test_first_and_repeated_setup(self):
        for cmdline in ('root=foo', f'root=foo azurefin.boot_uuid={UUID}'):
            self.assertEqual(setup.validate_host(self.mounts(), cmdline,
                             {'status': {'booted': {'image': {}}}}), UUID)

    def test_conflicting_uuid_and_live_boot_rejected(self):
        for cmdline in ('azurefin.boot_uuid=wrong', 'azurefin.live=1', 'rd.live.image',
                        f'azurefin.boot_uuid={UUID} azurefin.boot_uuid={UUID}'):
            with self.assertRaises(ValueError):
                setup.validate_host(self.mounts(), cmdline, {'status': {'booted': True}})

    def test_pending_deployment_and_unexpected_mount_rejected(self):
        for extra in ({'staged': {'image': {}}}, {'rollbackQueued': True},
                      {'usrOverlay': True}, {'booted': None}):
            with self.assertRaises(ValueError):
                setup.validate_host(self.mounts(), '', {'status': {'booted': True, **extra}})
        mounts = self.mounts()
        mounts['filesystems'][0]['options'] = 'ro'
        with self.assertRaises(ValueError):
            setup.validate_host(mounts, '', {'status': {'booted': True}})

    def test_provision_failure_never_changes_boot_arguments(self):
        with patch.object(Path, 'mkdir'), patch.object(setup, 'trusted_directory'), \
             patch.object(setup, 'provision', side_effect=ValueError('checksum mismatch')), \
             patch.object(setup, 'run') as run:
            with self.assertRaises(ValueError):
                setup.install_store(Path('/source'), {}, b'', UUID)
            run.assert_not_called()

    def test_verified_bundle_before_boot_opt_in(self):
        events = []
        with patch.object(Path, 'mkdir'), patch.object(setup, 'trusted_directory'), \
             patch.object(setup, 'provision', side_effect=lambda *args: events.append('provision')), \
             patch.object(setup, 'check_bundle', side_effect=lambda *args: events.append('verify')), \
             patch.object(setup, 'run', side_effect=lambda *args: events.append(args)):
            setup.install_store(Path('/source'), {}, b'', UUID)
        self.assertEqual(events[:2], ['provision', 'verify'])
        self.assertEqual(events[2], ('ostree', 'admin', 'instutil', 'set-kargs', '--merge',
                                    f'--replace=azurefin.boot_uuid={UUID}'))


if __name__ == '__main__':
    unittest.main()
