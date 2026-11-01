import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import setup_firmware_store as setup

UUID = 'a98d77ee-68a7-4863-8fca-843cc4808aba'


class StoreSetupTests(unittest.TestCase):
    def test_default_command_uses_store_without_private_image_rebuild(self):
        recipe = (Path(__file__).resolve().parent.parent / 'Containerfile.romulus').read_text()
        for name in ('azurefin-setup-firmware', 'azurefin-setup-firmware-store'):
            self.assertIn('ln -s /usr/libexec/azurefin/setup_firmware_store.py /usr/bin/' + name, recipe)
        self.assertNotIn('COPY surface/postinstall_firmware.py /usr/bin/azurefin-setup-firmware', recipe)
        self.assertIn('COPY surface/bluetooth_address.py /usr/libexec/azurefin/bluetooth_address.py', recipe)
        self.assertIn('/usr/bin/azurefin-setup-bluetooth', recipe)

    def test_extraction_space_floor(self):
        for free in (setup.MIN_EXTRACTION_FREE - 1, setup.MIN_EXTRACTION_FREE):
            with patch.object(setup.shutil, 'disk_usage', return_value=SimpleNamespace(free=free)):
                if free < setup.MIN_EXTRACTION_FREE:
                    with self.assertRaisesRegex(ValueError, '30 GiB'):
                        setup.check_extraction_space(Path('/state'))
                else:
                    setup.check_extraction_space(Path('/state'))

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
