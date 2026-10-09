import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('audit', Path(__file__).with_name('audit-release.py'))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AuditTests(unittest.TestCase):
    def test_forbidden_paths(self):
        for path in ('etc/romulus-bluetooth-address', 'tmp/update.msi',
                     'usr/lib/firmware/qcom/x1e80100/microsoft/Romulus/adspr.jsn',
                     'etc/ssh/ssh_host_ed25519_key', 'home/user/.ssh/authorized_keys',
                     'usr/etc/romulus-bluetooth-address',
                     'sysroot/ostree/deploy/fedora/deploy/example/etc/ssh/ssh_host_rsa_key',
                     'etc/NetworkManager/system-connections/wifi.nmconnection'):
            self.assertTrue(audit.forbidden(path), path)
        self.assertFalse(audit.forbidden('usr/libexec/romulus-bluetooth-address'))
        self.assertFalse(audit.forbidden('usr/lib/firmware/qcom/gen70500_gmu.bin'))

    def test_renamed_blob(self):
        with self.assertRaises(ValueError):
            audit.check_file('innocent', io.BytesIO(b'private'), 7,
                             {hashlib.sha256(b'private').hexdigest()})

    def test_nonempty_machine_id(self):
        with self.assertRaises(ValueError):
            audit.check_file('etc/machine-id', io.BytesIO(b'id'), 2, set())

    def test_metadata_exception_does_not_allow_surface_path(self):
        # Even with no denied content hash, destination-path protection remains.
        with self.assertRaises(ValueError):
            audit.check_file('usr/lib/firmware/qcom/x1e80100/microsoft/Romulus/adspr.jsn',
                             io.BytesIO(b'public metadata'), 15, set())

    def test_tar_scans_deleted_content(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'layer.tar'
            with tarfile.open(path, 'w') as archive:
                item = tarfile.TarInfo('tmp/update.msi')
                item.size = 3
                archive.addfile(item, io.BytesIO(b'msi'))
                archive.addfile(tarfile.TarInfo('tmp/.wh.update.msi'))
            with self.assertRaises(ValueError):
                audit.audit_tar(path, set())


if __name__ == '__main__':
    unittest.main()
