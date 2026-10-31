"""Release orchestration contracts; no builds, network calls or publication."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseLiveIsoTests(unittest.TestCase):
    def setUp(self):
        self.release = (ROOT / '.github/workflows/release-iso.yml').read_text()
        self.candidate = (ROOT / '.github/workflows/build-live-iso.yml').read_text()
        self.publisher = (ROOT / '.github/workflows/publish-sourceforge.yml').read_text()

    def test_only_successful_published_inputs_trigger_build(self):
        for contract in ("github.event.workflow_run.conclusion == 'success'",
                         "github.event.workflow_run.event == 'release'",
                         '<!-- azurefin:prebuilt-tested-iso -->',
                         "if: needs.policy.outputs.build == 'true'",
                         '.isDraft == false', 'cancel-in-progress: false'):
            self.assertIn(contract, self.release)

    def test_candidate_and_release_have_identical_signature_checks(self):
        def verification(text):
            return text.split('          for kind in base installer; do\n', 1)[1].split('          done\n', 1)[0]
        self.assertEqual(verification(self.release), verification(self.candidate))
        self.assertLess(self.release.index('cosign verify'), self.release.index('podman pull'))
        self.assertIn('--key surface/ota-signing.pub', self.release)
        self.assertIn('org.opencontainers.image.revision', self.release)
        self.assertNotIn('podman login', self.release)

    def test_live_composition_and_both_audits_gate_upload(self):
        self.assertIn('bash surface/65-compose-release-live-iso.sh', self.release)
        self.assertNotIn('bash surface/50-compose-release-iso.sh', self.release)
        for marker in ('FINAL_ISO_CONTENT_AUDIT_PASSED', 'LIVE_ISO_CANDIDATE_AUDIT_PASSED'):
            self.assertLess(self.release.index('grep -qx ' + marker), self.release.index('split -b'))
        for contract in ('size < 10000000000', '100 * 1024 * 1024',
                         '2>&1 | tee metadata/iso-audit.log',
                         'Hardware boot/install test: NOT YET RUN',
                         'if: always()', 'metadata/disk-usage.txt'):
            self.assertIn(contract, self.release)

    def test_sourceforge_runs_after_iso_without_replacing_files(self):
        self.assertIn('needs: iso', self.release)
        self.assertIn('uses: ./.github/workflows/publish-sourceforge.yml', self.release)
        compose = self.release.split('      - name: Compose and audit', 1)[1].split('      - name: Prepare', 1)[0]
        self.assertNotIn('GH_TOKEN', compose)
        self.assertNotIn('--clobber', self.release)
        self.assertNotIn('secrets: inherit', self.release)
        self.assertIn('mkdir /home/frs/project/$SOURCEFORGE_PROJECT/$RELEASE_TAG', self.publisher)
        self.assertIn('rsync -rcni', self.publisher)
        self.assertLess(self.publisher.index('Remote checksum verification failed'),
                        self.publisher.index('python3 surface/finalize_iso_release.py'))
        self.assertNotIn('rsync --delete', self.publisher)


if __name__ == '__main__':
    unittest.main()
