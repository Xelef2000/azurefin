import hashlib
from pathlib import Path
import tempfile
import unittest

from firmware_store_probe import inventory


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'qcom').mkdir()
        (self.root / 'qcom/fw').write_bytes(b'firmware')
        self.policy = {'files': [{'target': 'qcom/fw',
                                 'sha256': hashlib.sha256(b'firmware').hexdigest()}]}

    def test_valid(self):
        self.assertEqual(inventory(self.root, self.policy)['total_bytes'], 8)

    def test_corrupt(self):
        (self.root / 'qcom/fw').write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            inventory(self.root, self.policy)

    def test_missing(self):
        (self.root / 'qcom/fw').unlink()
        with self.assertRaises(FileNotFoundError):
            inventory(self.root, self.policy)

    def test_duplicate(self):
        self.policy['files'] *= 2
        with self.assertRaises(ValueError):
            inventory(self.root, self.policy)

    def test_traversal_and_absolute(self):
        for target in ('../fw', '/qcom/fw', 'qcom/../fw', 'qcom//fw'):
            self.policy['files'][0]['target'] = target
            with self.assertRaises(ValueError):
                inventory(self.root, self.policy)

    def test_file_symlink(self):
        (self.root / 'qcom/fw').unlink()
        (self.root / 'qcom/fw').symlink_to('/etc/passwd')
        with self.assertRaises(OSError):
            inventory(self.root, self.policy)

    def test_directory_symlink(self):
        (self.root / 'alias').symlink_to(self.root / 'qcom')
        self.policy['files'][0]['target'] = 'alias/fw'
        with self.assertRaises(OSError):
            inventory(self.root, self.policy)

    def test_empty_and_oversize(self):
        for size in (0, 64 * 1024 * 1024 + 1):
            with (self.root / 'qcom/fw').open('wb') as stream:
                stream.truncate(size)
            with self.assertRaises(ValueError):
                inventory(self.root, self.policy)
