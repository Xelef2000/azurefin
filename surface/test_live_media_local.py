"""Local live-media configuration and label-generation regression checks."""
import base64
import configparser
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

DIRECTORY = Path(__file__).parent / 'live-session'


def load(name):
    spec = importlib.util.spec_from_file_location(name, DIRECTORY / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LiveMediaTests(unittest.TestCase):
    def test_composer_uses_device_tree_from_live_kernel(self):
        exporter = (DIRECTORY / '40-export-vm.sh').read_text()
        composer = (DIRECTORY / '60-compose-local-iso.sh').read_text()
        self.assertIn('/usr/lib/modules/*/dtb/qcom/x1e80100-microsoft-romulus13.dtb', exporter)
        self.assertIn('-map "$artifacts/romulus13.dtb" /images/dtbs/qcom/x1e80100-microsoft-romulus13.dtb', composer)

    def test_composer_refreshes_and_verifies_provisioning_support(self):
        script = (DIRECTORY / '60-compose-local-iso.sh').read_text()
        self.assertIn('-rm_r /azurefin/support -- -map "$work/support" /azurefin/support', script)
        self.assertIn('-extract /azurefin/support "$work/verified-support"', script)
        self.assertIn('"$script_dir/.." "$work/verified-support"', script)
        audit = (DIRECTORY.parent / '51-audit-release-iso.sh').read_text()
        self.assertIn('verify_installer_support.py', audit)

    def test_combined_recipe_excludes_vm_diagnostics_and_requires_base(self):
        recipe = (DIRECTORY / 'Containerfile.live').read_text()
        self.assertIn('ARG BASE_IMAGE\nFROM ${BASE_IMAGE}', recipe)
        self.assertNotIn('localhost/', recipe)
        self.assertNotIn('vm-check', recipe)
        self.assertNotIn('Containerfile.vm', recipe)
        self.assertIn('azurefin-live-user.service', recipe)
        self.assertIn('azurefin-install.desktop', recipe)
        self.assertIn('surface/release-installer.ks /usr/share/anaconda/interactive-defaults.ks', recipe)
        self.assertIn("--omit 'anaconda ostree'", recipe)
        self.assertIn('bootloader-update.service', recipe)

    def test_live_installer_excludes_only_unused_optional_modules(self):
        config = configparser.ConfigParser()
        config.read(DIRECTORY / '90-azurefin-live.conf')
        self.assertEqual(set(config['Anaconda']['forbidden_modules'].split()), {
            'org.fedoraproject.Anaconda.Addons.Kdump',
            'org.fedoraproject.Anaconda.Modules.Subscription',
        })

    def test_installer_refuses_non_live_boot(self):
        launcher = load('launch-installer')
        with patch.object(launcher.os, 'geteuid', return_value=0), \
             patch.object(launcher.Path, 'read_text', return_value='quiet'), \
             patch.object(launcher, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'only available on live media'):
                launcher.main()
            run.assert_not_called()

    def test_installer_uses_separate_interactive_payload(self):
        recipe = (DIRECTORY / 'Containerfile.installer').read_text()
        self.assertIn('surface/release-installer.ks /usr/share/anaconda/interactive-defaults.ks', recipe)
        kickstart = (DIRECTORY.parent / 'release-installer.ks').read_text()
        self.assertIn('ostreecontainer --url=/run/install/repo/azurefin/base-oci', kickstart)
        for forbidden in ('liveimg ', 'autopart', 'clearpart', 'user --name=liveuser'):
            self.assertNotIn(forbidden, kickstart)
        desktop = (DIRECTORY / 'azurefin-install.desktop').read_text()
        self.assertIn('Terminal=false', desktop)
        self.assertIn('DBUS_SESSION_BUS_ADDRESS', desktop)
        launcher = (DIRECTORY / 'launch-installer.py').read_text()
        self.assertIn("'FSTYPE', '-T', '/run/overlayfs'", launcher)
        self.assertIn("os.environ['PKEXEC_UID'] = uid", launcher)

    def test_single_live_entry_without_installer_or_selinux_bypass(self):
        config = load('iso_grub').CONFIG
        self.assertEqual(config.count('menuentry '), 1)
        self.assertIn('root=live:LABEL=', config)
        self.assertIn('enforcing=1', config)
        self.assertNotIn('selinux=0', config)
        self.assertNotIn('inst.ks=', config)
        self.assertIn('AzurefinVM', config)
        self.assertIn('insmod /boot/grub2/arm64-efi/smbios.mod', config)
        self.assertIn('x1e80100-microsoft-romulus13.dtb', config)

    @unittest.skipUnless(Path('/etc/selinux/targeted/contexts/files/file_contexts').exists(),
                         'requires a local Fedora SELinux policy')
    def test_labels_are_generated_without_relabelling_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'root'
            policy = root / 'etc/selinux/targeted/contexts'
            policy.mkdir(parents=True)
            (policy / 'files').symlink_to('/etc/selinux/targeted/contexts/files')
            executable = root / 'usr/lib/systemd/systemd'
            executable.parent.mkdir(parents=True)
            executable.touch()
            objects = root / 'sysroot/ostree/repo/objects'
            objects.mkdir(parents=True)
            os.link(executable, objects / 'test.file')
            output = Path(directory) / 'labels'
            load('selinux_pseudo').generate(root, output)
            line = next(line for line in output.read_text().splitlines()
                        if line.startswith('"/usr/lib/systemd/systemd" '))
            context = base64.b64decode(line.split('=0s')[1])
            self.assertIn(b':init_exec_t:', context)
            self.assertNotIn('/sysroot/ostree', output.read_text())
            self.assertEqual(executable.read_bytes(), b'')


if __name__ == '__main__':
    unittest.main()
