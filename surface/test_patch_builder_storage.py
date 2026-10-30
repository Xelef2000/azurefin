import os
import unittest
from unittest.mock import patch

from patch_builder_storage import patch_buildroot, patch_storage


class BuilderStorageTests(unittest.TestCase):
    source = '''def options(storage_path, storage_path_empty):
        if True:
            podman_opts = [f"--root={storage_path_empty}", f"--imagestore={storage_path}"]
        return podman_opts
'''

    def options(self, fuse, installed=True, device_error=None):
        namespace = {'os': os}
        exec(compile(patch_storage(self.source), 'patched containers.py', 'exec'), namespace)
        with patch('os.path.exists', return_value=fuse) as exists, \
                patch('os.path.isfile', return_value=installed), \
                patch('os.open', return_value=42, side_effect=device_error) as opened, \
                patch('os.close') as closed:
            result = namespace['options']('/s', '/s2')
        if fuse:
            opened.assert_called_once_with('/dev/fuse', os.O_RDWR)
            closed.assert_called_once_with(42)
        else:
            opened.assert_not_called()
            closed.assert_not_called()
        exists.assert_called_once_with('/s/overlay/.has-mount-program')
        return result

    def test_shared_fuse_store_keeps_mount_program(self):
        self.assertEqual(self.options(True), [
            '--root=/s2', '--imagestore=/s', '--storage-opt',
            'overlay.mount_program=/usr/bin/fuse-overlayfs'])

    def test_native_store_unchanged(self):
        self.assertEqual(self.options(False), ['--root=/s2', '--imagestore=/s'])

    def test_missing_mount_program_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'requires fuse-overlayfs'):
            self.options(True, installed=False)

    def test_changed_upstream_source_rejected(self):
        for source in ('', self.source + self.source):
            with self.assertRaises(ValueError):
                patch_storage(source)

    def test_unavailable_fuse_device_fails_before_mount(self):
        for error in (FileNotFoundError(), PermissionError()):
            with self.subTest(error=error), self.assertRaisesRegex(RuntimeError, 'inside osbuild'):
                self.options(True, device_error=error)

    def test_private_device_setup_exposes_only_existing_fuse(self):
        source = '''def devices(self):
        if True:
            self._bind_dev(self.dev, "zero")
'''
        namespace = {'os': os}
        exec(compile(patch_buildroot(source), 'patched buildroot.py', 'exec'), namespace)
        from unittest.mock import Mock, call
        for present in (True, False):
            obj = Mock(dev='/private/dev')
            with patch('os.path.exists', return_value=present) as exists:
                namespace['devices'](obj)
            exists.assert_called_once_with('/dev/fuse')
            expected = [call('/private/dev', 'zero')]
            if present:
                expected.append(call('/private/dev', 'fuse'))
            self.assertEqual(obj._bind_dev.call_args_list, expected)

    def test_changed_device_setup_rejected(self):
        with self.assertRaises(ValueError):
            patch_buildroot('')
