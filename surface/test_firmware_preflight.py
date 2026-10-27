import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from firmware_bundle import manifest, provision
from firmware_preflight import MIN_FREE, check_bundle, check_space, trusted_directory, validate_mount


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.uuid = '11111111-2222-3333-4444-555555555555'
        self.mount = {'target': '/boot', 'fstype': 'ext4', 'uuid': self.uuid, 'options': 'rw,nosuid'}

    def validate(self, args=None):
        return validate_mount({'filesystems': [self.mount]},
                              args if args is not None else f'quiet azurefin.boot_uuid={self.uuid}')

    def test_valid_mount(self):
        self.assertEqual(self.validate(), self.uuid)

    def test_missing_duplicate_wrong_uuid(self):
        for args in ('quiet', 'azurefin.boot_uuid=invalid',
                     f'azurefin.boot_uuid={self.uuid} azurefin.boot_uuid={self.uuid}'):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.validate(args)

    def test_bad_mount(self):
        for key, value in (('target', '/'), ('fstype', 'btrfs'), ('uuid', None), ('options', 'ro')):
            with self.subTest(key=key), patch.dict(self.mount, {key: value}), self.assertRaises(ValueError):
                self.validate()

    def test_missing_mount(self):
        with self.assertRaises(ValueError):
            validate_mount({'filesystems': []}, '')

    def test_space_floor(self):
        check_space(MIN_FREE)
        with self.assertRaises(ValueError):
            check_space(MIN_FREE - 1)

    def test_bundle_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = {'files': [{'target': 'qcom/fw', 'sha256': hashlib.sha256(b'fw').hexdigest()}]}
            contents = manifest(policy)
            bundle = root / 'azurefin/firmware' / hashlib.sha256(contents).hexdigest()
            (bundle / 'qcom').mkdir(parents=True)
            (bundle / 'qcom/fw').write_bytes(b'fw')
            # Temp trees are owned by the test runner; ownership has separate tests.
            with patch('firmware_preflight.trusted_directory'):
                self.assertEqual(check_bundle(root, policy, contents)['files'], 1)
                with self.assertRaises(ValueError):
                    check_bundle(root, policy, b'wrong manifest')
                (bundle / 'qcom/fw').write_bytes(b'bad')
                with self.assertRaises(ValueError):
                    check_bundle(root, policy, contents)

    def test_trusted_directory(self):
        class Info:
            st_mode = 0o40700
            st_uid = 0
        with patch.object(Path, 'lstat', return_value=Info()):
            trusted_directory(Path('/unused'))
            for mode, uid in ((0o120777, 0), (0o40777, 0), (0o40700, 1000)):
                with patch.object(Info, 'st_mode', mode), patch.object(Info, 'st_uid', uid):
                    with self.assertRaises(ValueError):
                        trusted_directory(Path('/unused'))

    def test_new_policy_requires_new_bundle_and_preserves_old(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = root / 'azurefin/firmware'
            store.mkdir(parents=True)
            source = root / 'source'
            (source / 'qcom').mkdir(parents=True)
            (source / 'qcom/fw').write_bytes(b'old')
            old_policy = {'files': [{'target': 'qcom/fw',
                                    'sha256': hashlib.sha256(b'old').hexdigest()}]}
            old_bundle = provision(source, store, old_policy)
            new_policy = {'files': [{'target': 'qcom/fw',
                                    'sha256': hashlib.sha256(b'new').hexdigest()}]}
            with patch('firmware_preflight.trusted_directory'):
                with self.assertRaises(FileNotFoundError):
                    check_bundle(root, new_policy, manifest(new_policy))
                self.assertEqual(check_bundle(root, old_policy, manifest(old_policy))['files'], 1)
                (source / 'qcom/fw').write_bytes(b'new')
                provision(source, store, new_policy)
                self.assertEqual(check_bundle(root, new_policy, manifest(new_policy))['files'], 1)
                self.assertEqual(check_bundle(root, old_policy, manifest(old_policy))['files'], 1)
            self.assertEqual((old_bundle / 'qcom/fw').read_bytes(), b'old')


if __name__ == '__main__':
    unittest.main()
