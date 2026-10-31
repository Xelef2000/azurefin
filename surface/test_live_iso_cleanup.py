"""Exercise the real composer with tiny ISO/EFI fixtures, without host mounts."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SURFACE = Path(__file__).parent
TOOLS = ('xorriso', 'mformat', 'mmd', 'mcopy', 'grub2-script-check',
         'implantisomd5', 'checkisomd5')


def run(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True,
                          env={**os.environ, 'GITHUB_ACTIONS': 'false'}).stdout


@unittest.skipUnless(all(shutil.which(tool) for tool in TOOLS), 'ISO tools required')
class LiveIsoCleanupTests(unittest.TestCase):
    def test_original_and_already_live_seeds_remove_only_obsolete_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tree = root / 'tree'
            for name in ('images', 'EFI/BOOT', 'azurefin', 'keep'):
                (tree / name).mkdir(parents=True)
            cfg = tree / 'EFI/BOOT/grub.cfg'
            cfg.write_text('set timeout=5\n')
            for name in ('osbuild.ks', 'osbuild-base.ks', 'images/install.img',
                         'keep/install.img', 'azurefin/fixture'):
                (tree / name).write_text(name)
            efi = tree / 'images/efiboot.img'
            run('mformat', '-C', '-i', str(efi), '-T', '40960', '::')
            run('mmd', '-i', str(efi), '::/EFI', '::/EFI/BOOT')
            run('mcopy', '-i', str(efi), str(cfg), '::/EFI/BOOT/grub.cfg')
            source = root / 'seed.iso'
            run('xorriso', '-as', 'mkisofs', '-R', '-J', '-V', 'Fedora-S-dvd-aarch64-44',
                '-e', 'images/efiboot.img', '-no-emul-boot',
                '-o', str(source), str(tree))
            # Reproduce the old false-negative: exit code 1 is invalid for
            # -return_with, so the probe fails before even looking up the file.
            probe = subprocess.run(['xorriso', '-return_with', 'WARNING', '1',
                                    '-indev', str(source), '-ls', '/images/install.img'],
                                   text=True, capture_output=True)
            self.assertNotEqual(probe.returncode, 0)
            self.assertIn('Not an allowed exit_value', probe.stderr)
            artifacts = root / 'artifacts'
            artifacts.mkdir()
            for name in ('root.squashfs', 'initrd', 'vmlinuz', 'smbios.mod', 'romulus13.dtb'):
                (artifacts / name).write_text('fixture ' + name)
            # Desktop mode normally removes /azurefin. Re-add the fixture to
            # the live seed so the second invocation tests the same mode.
            for index in range(2):
                output = root / f'live-{index}.iso'
                try:
                    run('bash', str(SURFACE / 'live-session/60-compose-local-iso.sh'),
                        str(source), str(artifacts), str(output), 'desktop')
                except subprocess.CalledProcessError as error:
                    self.fail(error.stdout + error.stderr)
                extracted = root / f'extracted-{index}'
                run('xorriso', '-osirrox', 'on', '-indev', str(output),
                    '-extract', '/', str(extracted))
                for name in ('osbuild.ks', 'osbuild-base.ks', 'images/install.img'):
                    self.assertFalse((extracted / name).exists(), name)
                self.assertEqual((extracted / 'keep/install.img').read_text(), 'keep/install.img')
                self.assertEqual((extracted / 'LiveOS/squashfs.img').read_bytes(),
                                 (artifacts / 'root.squashfs').read_bytes())
                source = root / f'live-seed-{index}.iso'
                run('xorriso', '-indev', str(output), '-outdev', str(source),
                    '-boot_image', 'any', 'replay', '-map', str(tree / 'azurefin'),
                    '/azurefin', '-commit', '-end')
