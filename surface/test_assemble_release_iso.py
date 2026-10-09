import hashlib
from pathlib import Path
import tempfile
import unittest
from assemble_release_iso import assemble


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'parts'
        self.source.mkdir()
        self.output = Path(self.temp.name) / 'upload'
        self.tag = 'v0.0.1-alpha'
        self.name = f'azurefin-{self.tag}-aarch64.iso'
        chunks = [b'first', b'second']
        manifest = []
        for index, data in enumerate(chunks):
            name = f'{self.name}.part-{index:03d}'
            (self.source / name).write_bytes(data)
            manifest.append(f'{hashlib.sha256(data).hexdigest()}  ./{name}\n')
        (self.source / 'SHA256SUMS').write_text(''.join(manifest))
        (self.source / 'ISO-SHA256SUM').write_text(
            f'{hashlib.sha256(b"".join(chunks)).hexdigest()}  {self.name}\n')
        (self.source / 'iso-audit.log').write_text('FINAL_ISO_CONTENT_AUDIT_PASSED\n')
        (self.source / 'BUILD-INFO.txt').write_text('test\n')

    def test_valid(self):
        assemble(self.tag, self.source, self.output)
        self.assertEqual((self.output / self.name).read_bytes(), b'firstsecond')
        self.assertEqual(len(list(self.output.iterdir())), 4)
        with self.assertRaises(FileExistsError):
            assemble(self.tag, self.source, self.output)

    def test_corrupt_chunk(self):
        (self.source / f'{self.name}.part-000').write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError, 'Chunk checksum'):
            assemble(self.tag, self.source, self.output)

    def test_bad_whole_checksum(self):
        (self.source / 'ISO-SHA256SUM').write_text(f'{"0" * 64}  {self.name}')
        with self.assertRaisesRegex(ValueError, 'Whole ISO checksum'):
            assemble(self.tag, self.source, self.output)

    def test_missing_audit(self):
        (self.source / 'iso-audit.log').write_text('failed\n')
        with self.assertRaisesRegex(ValueError, 'audit'):
            assemble(self.tag, self.source, self.output)

    def test_unsafe_manifest(self):
        (self.source / 'SHA256SUMS').write_text(f'{"0" * 64}  /etc/passwd\n')
        with self.assertRaisesRegex(ValueError, 'chunk checksum entry'):
            assemble(self.tag, self.source, self.output)

    def test_missing_chunk(self):
        manifest = self.source / 'SHA256SUMS'
        manifest.write_text(manifest.read_text().splitlines()[1] + '\n')
        with self.assertRaisesRegex(ValueError, 'Missing or duplicate'):
            assemble(self.tag, self.source, self.output)

    def test_size_limit(self):
        with (self.source / f'{self.name}.part-000').open('wb') as handle:
            handle.truncate(10_000_000_000)
        with self.assertRaisesRegex(ValueError, '10 GB limit'):
            assemble(self.tag, self.source, self.output)
        self.assertFalse(self.output.exists())
