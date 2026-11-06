import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from verify_artifact import verify


class ArtifactTests(unittest.TestCase):
    def test_published_sources_match_arm64_installer_pin(self):
        manifest = json.loads(Path(__file__).with_name('artifacts.json').read_text())
        release = manifest['source_release']
        self.assertEqual(release['architecture'], 'aarch64-linux')
        self.assertEqual(release['installer_sha256'], manifest['artifacts']['aarch64-linux']['sha256'])
        for kind in ('sources', 'notices'):
            self.assertGreater(release[kind]['bytes'], 0)
            self.assertRegex(release[kind]['sha256'], r'^[0-9a-f]{64}$')
            self.assertTrue(release[kind]['url'].startswith(
                release['url'].replace('/tag/', '/download/') + '/'))

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "installer"
        header = bytearray(20)
        header[:6] = b"\x7fELF\x02\x01"
        struct.pack_into("<H", header, 18, 183)
        self.path.write_bytes(header)
        self.pin = {"bytes": len(header), "elf_machine": 183,
                    "sha256": hashlib.sha256(header).hexdigest()}

    def test_valid(self):
        verify(self.path, self.pin)

    def test_wrong_size(self):
        self.pin["bytes"] += 1
        with self.assertRaises(ValueError):
            verify(self.path, self.pin)

    def test_wrong_hash(self):
        self.pin["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            verify(self.path, self.pin)

    def test_wrong_architecture(self):
        self.pin["elf_machine"] = 62
        with self.assertRaises(ValueError):
            verify(self.path, self.pin)

    def test_non_elf(self):
        data = b"not an ELF executable"
        self.path.write_bytes(data)
        self.pin.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        with self.assertRaises(ValueError):
            verify(self.path, self.pin)
