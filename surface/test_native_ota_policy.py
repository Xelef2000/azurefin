"""Native trust wiring; cryptographic cases are tested by scripts/test-native-signatures.py."""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parent
REPOSITORY = 'ghcr.io/xelef2000/azurefin'


class NativePolicyTests(unittest.TestCase):
    def test_repository_signature_required_without_alternative_accept_rule(self):
        policy = json.loads((ROOT / 'native-ota/policy.json').read_text())
        self.assertEqual(policy['default'], [{'type': 'reject'}])
        docker = policy['transports']['docker']
        self.assertEqual(set(docker), {'', REPOSITORY})
        self.assertEqual(docker[REPOSITORY], [{
            'type': 'sigstoreSigned',
            'keyPath': '/usr/lib/pki/containers/azurefin-ota.pub',
            'signedIdentity': {'type': 'exactRepository', 'dockerRepository': REPOSITORY},
        }])

    def test_public_key_fingerprint(self):
        der = subprocess.check_output(['openssl', 'pkey', '-pubin', '-in',
                                      str(ROOT / 'ota-signing.pub'), '-outform', 'DER'])
        self.assertEqual(hashlib.sha256(der).hexdigest(),
                         'c784e8b27ac8400842a580c9a8e6bb1c123555ca37812641365b69c0a18fbd65')

    def test_image_installs_policy_key_and_attachment_lookup(self):
        recipe = (ROOT.parent / 'Containerfile.romulus').read_text()
        for line in (
            'COPY surface/ota-signing.pub /usr/lib/pki/containers/azurefin-ota.pub',
            'COPY surface/native-ota/policy.json /etc/containers/policy.json',
            'COPY surface/native-ota/azurefin.yaml /etc/containers/registries.d/azurefin.yaml',
        ):
            self.assertIn(line, recipe)
        self.assertIn(f'  {REPOSITORY}:\n    use-sigstore-attachments: true',
                      (ROOT / 'native-ota/azurefin.yaml').read_text())

    def test_development_transports_remain_usable(self):
        policy = json.loads((ROOT / 'native-ota/policy.json').read_text())
        for transport in ('docker', 'containers-storage', 'dir', 'oci', 'oci-archive'):
            self.assertEqual(policy['transports'][transport][''],
                             [{'type': 'insecureAcceptAnything'}])


if __name__ == '__main__':
    unittest.main()
