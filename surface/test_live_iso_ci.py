"""Safety and orchestration contracts for the manual live ISO candidate."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LiveIsoCITests(unittest.TestCase):
    def test_public_runner_probe_is_default_and_read_only(self):
        text = (ROOT / '.github/workflows/build-live-iso.yml').read_text()
        self.assertIn('capacity_only:', text)
        self.assertIn('default: true', text)
        self.assertIn('if: ${{ !inputs.capacity_only }}', text)
        probe = text.split('  capacity:\n', 1)[1].split('  live:\n', 1)[0]
        self.assertIn('runs-on: ubuntu-24.04-arm', probe)
        self.assertIn('df -B1', probe)
        for forbidden in ('sudo ', 'rm ', 'podman pull', 'docker pull', 'mkfs', 'mount '):
            self.assertNotIn(forbidden, probe)

    def test_invalid_invocation_fails_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'must-not-exist'
            result = subprocess.run(
                ['bash', str(ROOT / 'surface/65-compose-release-live-iso.sh'),
                 'mutable:latest', 'mutable:latest', str(output), 'bad-revision'],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_candidate_cannot_publish(self):
        text = (ROOT / '.github/workflows/build-live-iso.yml').read_text()
        self.assertIn('workflow_dispatch:', text)
        for forbidden in ('  release:', 'workflow_run:', 'contents: write',
                          'packages: write', 'gh release', 'sourceforge',
                          'SOURCEFORGE_SSH_KEY', 'secrets: inherit'):
            self.assertNotIn(forbidden, text)
        self.assertIn('persist-credentials: false', text)
        self.assertIn('Hardware boot/install test: NOT YET RUN', text)
        self.assertIn('retention-days: 7', text)

    def test_inputs_are_verified_before_pull(self):
        text = (ROOT / '.github/workflows/build-live-iso.yml').read_text()
        self.assertIn('--certificate-identity', text)
        self.assertIn('--key surface/ota-signing.pub', text)
        self.assertIn('org.opencontainers.image.revision', text)
        self.assertLess(text.index('cosign verify'), text.index('podman pull'))
        self.assertIn('"docker://$ref"', text)
        self.assertIn('165 * 1024 * 1024', text)

    def test_live_audit_follows_composition(self):
        text = (ROOT / 'surface/65-compose-release-live-iso.sh').read_text()
        self.assertIn('--network=none', text)
        self.assertIn('audit-release.py" oci "$output/live-oci"', text)
        self.assertIn('30-test-container.sh" "$live"', text)
        self.assertIn('150 * 1024 * 1024', text)
        self.assertLess(text.index('50-compose-release-iso.sh'), text.index('podman build'))
        self.assertLess(text.index('60-compose-local-iso.sh'), text.index('51-audit-release-iso.sh'))
        self.assertIn('"$output/final-audit" live', text)
        self.assertTrue(text.rstrip().endswith('echo LIVE_ISO_CANDIDATE_AUDIT_PASSED'))
        workflow = (ROOT / '.github/workflows/build-live-iso.yml').read_text()
        self.assertIn('grep -qx LIVE_ISO_CANDIDATE_AUDIT_PASSED', workflow)
        self.assertLess(workflow.index('grep -qx'), workflow.index('split -b'))


if __name__ == '__main__':
    unittest.main()
