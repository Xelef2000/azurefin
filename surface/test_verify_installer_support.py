import shutil
import tempfile
import unittest
from pathlib import Path

from verify_installer_support import FILES, verify


class SupportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(__file__).parent
        self.shipped = Path(self.tmp.name)
        shutil.copytree(self.source / 'build', self.shipped / 'build')
        for name in FILES:
            shutil.copyfile(self.source / name, self.shipped / name)

    def test_current_bundle_passes(self):
        verify(self.source, self.shipped)

    def test_old_recipe_fails(self):
        (self.shipped / 'Containerfile.provision').write_text('RUN bootc container lint\n')
        with self.assertRaisesRegex(ValueError, 'Stale provisioning file'):
            verify(self.source, self.shipped)

    def test_missing_cleanup_fails(self):
        (self.shipped / 'build/29-clean-build-state.sh').unlink()
        with self.assertRaisesRegex(ValueError, 'file set differs'):
            verify(self.source, self.shipped)

    def test_extra_old_file_fails(self):
        (self.shipped / 'build/obsolete.sh').touch()
        with self.assertRaisesRegex(ValueError, 'file set differs'):
            verify(self.source, self.shipped)

    def test_symlink_fails(self):
        path = self.shipped / 'Containerfile.provision'
        path.unlink()
        path.symlink_to(self.source / 'Containerfile.provision')
        with self.assertRaisesRegex(ValueError, 'symlinked'):
            verify(self.source, self.shipped)
