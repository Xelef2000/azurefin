"""Offline installation must leave a signed registry origin for later updates."""
import json
from pathlib import Path
import shlex
import tomllib
import unittest

ROOT = Path(__file__).resolve().parent.parent


class InstallerChannelTests(unittest.TestCase):
    def test_both_installer_hooks_use_contract_channel_offline(self):
        contract = json.loads((ROOT / 'surface/update-contract.json').read_text())
        kickstarts = [
            (ROOT / 'surface/release-installer.ks').read_text(),
            tomllib.loads((ROOT / 'iso/iso.toml').read_text())[
                'customizations']['installer']['kickstart']['contents'],
        ]
        expected = ['bootc', 'switch', '--mutate-in-place', '--transport',
                    'registry', '--enforce-container-sigpolicy', contract['channel']]
        for ks in kickstarts:
            with self.subTest(kickstart=ks):
                hooks = [block for block in ks.split('%post ')[1:]
                         if 'bootc switch' in block.split('%end')[0]]
                self.assertEqual(len(hooks), 1)
                header, body = hooks[0].split('\n', 1)
                self.assertIn('--erroronfail', header)
                self.assertNotIn('--nochroot', header)
                self.assertIn('--log=/var/log/azurefin-update-channel-post.log', header)
                commands = [shlex.split(line) for line in body.split('%end')[0].splitlines()
                            if line.startswith('bootc ')]
                self.assertEqual(commands, [expected])
                self.assertNotIn('--apply', body)
                self.assertNotIn('--no-signature-verification', body)

    def test_install_source_remains_local_and_interactive(self):
        ks = (ROOT / 'surface/release-installer.ks').read_text()
        self.assertIn('ostreecontainer --url=/run/install/repo/azurefin/base-oci --transport=oci', ks)
        self.assertNotIn('clearpart', ks)
        self.assertNotIn('reboot', '\n'.join(
            line for line in ks.splitlines() if not line.startswith('#')))

    def test_live_installer_uses_updated_kickstart(self):
        recipe = (ROOT / 'surface/live-session/Containerfile.live').read_text()
        self.assertIn('install -Dm644 /run/azurefin-source/release-installer.ks /usr/share/anaconda/interactive-defaults.ks', recipe)


if __name__ == '__main__':
    unittest.main()
