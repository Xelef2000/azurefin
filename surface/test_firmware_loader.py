import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from firmware_bundle import manifest


class LoaderTests(unittest.TestCase):
    """Run the actual shell loader with fake storage discovery/mount commands."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ('run', 'etc/azurefin', 'bin', 'fixture'):
            (self.root / name).mkdir(parents=True)
        self.uuid = '11111111-2222-3333-4444-555555555555'
        self.cmdline = self.root / 'cmdline'
        self.cmdline.write_text(f'quiet azurefin.boot_uuid={self.uuid}\n')
        (self.root / 'uptime').write_text('1.00 2.00\n')
        self.parameter = self.root / 'firmware-path'
        self.parameter.write_text('')
        policy = {'files': [{'target': 'qcom/fw',
                            'sha256': hashlib.sha256(b'firmware').hexdigest()}]}
        contents = manifest(policy)
        (self.root / 'etc/azurefin/boot-firmware.sha256').write_bytes(contents)
        self.bundle = self.root / 'fixture/azurefin/firmware' / hashlib.sha256(contents).hexdigest()
        (self.bundle / 'qcom').mkdir(parents=True)
        (self.bundle / 'qcom/fw').write_bytes(b'firmware')
        commands = {
            'modprobe': 'exit 0',
            'blkid': 'echo /dev/fake',
            'mount': 'cp -a "$FIXTURE/." "${@: -1}"',
            'umount': 'exit 0',
        }
        for name, body in commands.items():
            command = self.root / 'bin' / name
            command.write_text('#!/bin/bash\n' + body + '\n')
            command.chmod(0o755)
        source = Path(__file__).parent / 'dracut/91azurefin-firmware/load-firmware.sh'
        script = source.read_text()
        for old, new in (
            ('/proc/cmdline', self.cmdline), ('/proc/uptime', self.root / 'uptime'),
            ('/sys/module/firmware_class/parameters/path', self.parameter),
            ('/etc/azurefin', self.root / 'etc/azurefin'), ('/run/', str(self.root / 'run') + '/'),
        ):
            script = script.replace(old, str(new))
        self.script = self.root / 'loader.sh'
        self.script.write_text(script)

    def run_loader(self):
        env = dict(os.environ, PATH=f'{self.root}/bin:' + os.environ['PATH'],
                   FIXTURE=str(self.root / 'fixture'))
        return subprocess.run(['bash', str(self.script)], env=env, capture_output=True)

    def assert_rejected(self):
        self.assertNotEqual(self.run_loader().returncode, 0)
        self.assertEqual(self.parameter.read_text(), '')
        self.assertFalse((self.root / 'run/azurefin-firmware').exists())

    def test_valid(self):
        self.assertEqual(self.run_loader().returncode, 0)
        runtime = self.root / 'run/azurefin-firmware'
        self.assertEqual(self.parameter.read_text(), str(runtime))
        self.assertEqual((runtime / 'qcom/fw').read_bytes(), b'firmware')

    def test_corrupt(self):
        (self.bundle / 'qcom/fw').write_bytes(b'corrupt')
        self.assert_rejected()

    def test_missing(self):
        (self.bundle / 'qcom/fw').unlink()
        self.assert_rejected()

    def test_symlink(self):
        (self.bundle / 'qcom/fw').unlink()
        (self.bundle / 'qcom/fw').symlink_to('/etc/passwd')
        self.assert_rejected()

    def test_duplicate_uuid(self):
        self.cmdline.write_text(f'azurefin.boot_uuid={self.uuid} azurefin.boot_uuid={self.uuid}\n')
        self.assert_rejected()

    def test_invalid_uuid(self):
        self.cmdline.write_text('azurefin.boot_uuid=../../bad\n')
        self.assert_rejected()

    def test_installer_without_opt_in(self):
        self.cmdline.write_text('quiet\n')
        self.assertEqual(self.run_loader().returncode, 0)
        self.assertEqual(self.parameter.read_text(), '')
