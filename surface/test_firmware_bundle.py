import errno
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from firmware_bundle import manifest, provision


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source, self.store = root / 'source', root / 'store'
        (self.source / 'qcom').mkdir(parents=True)
        self.store.mkdir()
        (self.source / 'qcom/fw').write_bytes(b'firmware')
        self.policy = {'files': [{'target': 'qcom/fw',
                                 'sha256': hashlib.sha256(b'firmware').hexdigest()}]}

    def test_complete_and_idempotent(self):
        result = provision(self.source, self.store, self.policy)
        self.assertEqual(result.name, hashlib.sha256(manifest(self.policy)).hexdigest())
        self.assertEqual((result / 'qcom/fw').read_bytes(), b'firmware')
        self.assertEqual(provision(self.source, self.store, self.policy), result)
        self.assertEqual(len(list(self.store.iterdir())), 1)

    def test_msi_version_does_not_change_bundle_id(self):
        self.assertEqual(manifest(self.policy), manifest(dict(self.policy, version='new-msi')))

    def test_preserves_old_bundle(self):
        old = provision(self.source, self.store, self.policy)
        (self.source / 'qcom/fw').write_bytes(b'new firmware')
        self.policy['files'][0]['sha256'] = hashlib.sha256(b'new firmware').hexdigest()
        new = provision(self.source, self.store, self.policy)
        self.assertNotEqual(old, new)
        self.assertEqual((old / 'qcom/fw').read_bytes(), b'firmware')

    def test_corrupt_source_not_published(self):
        (self.source / 'qcom/fw').write_bytes(b'bad')
        with self.assertRaises(ValueError):
            provision(self.source, self.store, self.policy)
        self.assertEqual(list(self.store.iterdir()), [])

    def test_corrupt_existing_bundle_not_overwritten(self):
        old = provision(self.source, self.store, self.policy)
        (old / 'qcom/fw').write_bytes(b'bad')
        with self.assertRaises(ValueError):
            provision(self.source, self.store, self.policy)
        self.assertEqual((old / 'qcom/fw').read_bytes(), b'bad')

    def test_disk_full_before_publish(self):
        with patch('firmware_bundle.os.fsync', side_effect=OSError(errno.ENOSPC, 'full')):
            with self.assertRaises(OSError):
                provision(self.source, self.store, self.policy)
        self.assertEqual(list(self.store.iterdir()), [])

    def test_interrupted_copy_not_published(self):
        with patch('firmware_bundle.copy_verified', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                provision(self.source, self.store, self.policy)
        self.assertEqual(list(self.store.iterdir()), [])

    def test_disk_full_on_file_creation(self):
        with patch('firmware_bundle.Path.open', side_effect=OSError(errno.ENOSPC, 'full')):
            with self.assertRaises(OSError):
                provision(self.source, self.store, self.policy)
        self.assertEqual(list(self.store.iterdir()), [])

    def test_abandoned_temporary_bundle_is_not_selected(self):
        abandoned = self.store / '.preparing-interrupted'
        abandoned.mkdir()
        (abandoned / 'partial').write_bytes(b'partial')
        result = provision(self.source, self.store, self.policy)
        self.assertNotEqual(result, abandoned)
        self.assertEqual((result / 'qcom/fw').read_bytes(), b'firmware')
        self.assertTrue(abandoned.exists())

    def test_symlink_store_rejected(self):
        alias = self.store.parent / 'alias'
        alias.symlink_to(self.store)
        with self.assertRaises(ValueError):
            provision(self.source, alias, self.policy)

    def test_symlink_source_rejected(self):
        (self.source / 'qcom/fw').unlink()
        (self.source / 'qcom/fw').symlink_to('/etc/passwd')
        with self.assertRaises(OSError):
            provision(self.source, self.store, self.policy)
        self.assertEqual(list(self.store.iterdir()), [])

    def test_invalid_policy_rejected(self):
        for target in ('../escape', '/absolute', 'qcom//fw', '.', 'qcom/fw\nother'):
            with self.subTest(target=target):
                self.policy['files'][0]['target'] = target
                with self.assertRaises(ValueError):
                    provision(self.source, self.store, self.policy)
        self.assertEqual(list(self.store.iterdir()), [])

    def test_manifest_order_independent(self):
        other = dict(self.policy['files'][0], target='qcom/other')
        first = {'files': [self.policy['files'][0], other]}
        second = {'files': list(reversed(first['files']))}
        self.assertEqual(manifest(first), manifest(second))
