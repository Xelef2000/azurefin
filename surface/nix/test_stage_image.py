import hashlib
import io
import json
from pathlib import Path
import tempfile
import tarfile
import unittest
from unittest.mock import patch, MagicMock

from stage_image import notice_path, stage, unpack_notices, verify_asset, RUNTIME_FILES, UNITS


class ImageStagingTests(unittest.TestCase):
    def test_notice_archive_rejects_links_and_duplicate_members(self):
        for duplicate in (False, True):
            data = io.BytesIO()
            with tarfile.open(fileobj=data, mode='w') as archive:
                member = tarfile.TarInfo('notices/index.json')
                if duplicate:
                    member.size = 2
                    archive.addfile(member, io.BytesIO(b'{}'))
                    archive.addfile(member, io.BytesIO(b'{}'))
                else:
                    member.type = tarfile.SYMTYPE
                    member.linkname = '/etc/passwd'
                    archive.addfile(member)
            process = MagicMock()
            process.__enter__.return_value = process
            process.stdout = io.BytesIO(data.getvalue())
            process.wait.return_value = 0
            with tempfile.TemporaryDirectory() as temp, patch('stage_image.subprocess.Popen', return_value=process):
                with self.assertRaises(ValueError):
                    unpack_notices(Path('fixture'), Path(temp))

    def test_existing_store_is_not_hidden(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'nix').mkdir()
            (root / 'nix/keep').write_text('foreign')
            with patch('stage_image.verify'), patch('stage_image.verify_asset'):
                with self.assertRaises(ValueError):
                    stage(root, root / 'installer', root / 'notices')
            self.assertEqual((root / 'nix/keep').read_text(), 'foreign')
            self.assertFalse((root / 'usr').exists())

    def test_notice_path_allowlist(self):
        self.assertEqual(notice_path('notices/index.json'), 'notices/index.json')
        self.assertEqual(notice_path('notices/texts/' + 'a' * 64 + '.txt'),
                         'notices/texts/' + 'a' * 64 + '.txt')
        for name in ('/etc/passwd', '../etc/passwd', 'notices/../passwd', 'notices/private.txt'):
            with self.assertRaises(ValueError):
                notice_path(name)

    def test_asset_digest_and_size(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'asset'
            path.write_bytes(b'notices')
            pin = {'bytes': 7, 'sha256': hashlib.sha256(b'notices').hexdigest()}
            verify_asset(path, pin)
            for bad in (pin | {'bytes': 8}, pin | {'sha256': '0' * 64}):
                with self.assertRaises(ValueError):
                    verify_asset(path, bad)

    def test_only_runtime_files_staged_and_no_mutable_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'image'
            root.mkdir()
            installer = Path(temp) / 'installer'
            installer.write_bytes(b'fixture')
            def notices(_archive, target):
                (target / 'notices').mkdir()
                (target / 'notices/index.json').write_text('{}')
            with patch('stage_image.verify'), patch('stage_image.verify_asset'), patch('stage_image.unpack_notices', side_effect=notices):
                stage(root, installer, Path(temp) / 'notices')
            resources = root / 'usr/share/azurefin/nix'
            self.assertEqual({p.name for p in resources.iterdir()}, set(RUNTIME_FILES) | {'installed-image.json'})
            self.assertEqual(json.loads((resources / 'installed-image.json').read_text()), {'schema': 1})
            self.assertEqual({p.name for p in (root / 'usr/lib/systemd/system').iterdir()}, set(UNITS))
            self.assertEqual(str((root / 'etc/systemd/system/timers.target.wants/azurefin-nix-ready.timer').readlink()),
                             '/usr/lib/systemd/system/azurefin-nix-ready.timer')
            self.assertFalse((root / 'var').exists())
            self.assertFalse((root / 'etc/nix').exists())
            self.assertFalse((root / 'nix').is_symlink())
            self.assertEqual(list((root / 'nix').iterdir()), [])
            self.assertTrue((root / 'usr/share/licenses/azurefin-nix/Azurefin-LICENSE').is_file())

    def test_shared_image_stage_and_derived_image_inheritance(self):
        root = Path(__file__).resolve().parents[2]
        container = (root / 'Containerfile.romulus').read_text()
        self.assertLess(container.index('bash /ctx/build/15-nix.sh'), container.index('FROM packages AS local-image'))
        self.assertNotIn('15-nix.sh', (root / 'Containerfile.romulus-local').read_text())


if __name__ == '__main__':
    unittest.main()
