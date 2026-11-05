import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from inventory_notices import retain, selected


class NoticeTests(unittest.TestCase):
    def test_filename_rules_and_explicit_exception(self):
        for name in ('COPYING.RUNTIME', 'LICENSES/LLVM-exception.txt', 'nested/NOTICE.md',
                     'COPYRIGHTS', 'LICENCES.txt', 'NOTICES'):
            self.assertTrue(selected(name, []))
        self.assertFalse(selected('README.md', []))
        self.assertTrue(selected('README.md', ['README.md']))

    def test_unsafe_names_rejected(self):
        for name in ('../LICENSE', '/LICENSE'):
            with self.assertRaises(ValueError):
                selected(name, [])

    def test_archive_read_without_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / 'sources.tar'
            with tarfile.open(archive, 'w') as output:
                member = tarfile.TarInfo('project/LICENSE')
                member.size = 5
                output.addfile(member, io.BytesIO(b'terms'))
                link = tarfile.TarInfo('project/COPYING')
                link.type = tarfile.SYMTYPE
                link.linkname = '/etc/passwd'
                output.addfile(link)
            destination = root / 'texts'
            destination.mkdir()
            report = retain(archive, destination)
            self.assertEqual(len(report['notices']), 1)
            self.assertEqual(next(destination.iterdir()).read_bytes(), b'terms')
            self.assertFalse((root / 'project').exists())

    def test_missing_explicit_notice_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                retain(root, root, ['missing'])


if __name__ == '__main__':
    unittest.main()
