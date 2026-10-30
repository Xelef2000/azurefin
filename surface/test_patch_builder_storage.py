import os
import unittest
from unittest.mock import patch

from patch_builder_storage import patch_storage


class BuilderStorageTests(unittest.TestCase):
    source = '''def options(storage_path, storage_path_empty):
        if True:
            podman_opts = [f"--root={storage_path_empty}", f"--imagestore={storage_path}"]
        return podman_opts
'''

    def options(self, fuse, installed=True):
        namespace = {'os': os}
        exec(compile(patch_storage(self.source), 'patched containers.py', 'exec'), namespace)
        with patch('os.path.exists', return_value=fuse) as exists, \
                patch('os.path.isfile', return_value=installed):
            result = namespace['options']('/s', '/s2')
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
