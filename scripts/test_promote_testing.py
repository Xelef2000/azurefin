"""Offline orchestration tests; fake credentials and registry, no publication."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().with_name('promote-testing.sh')


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'bin').mkdir()
        for command in ('cosign', 'skopeo'):
            mock = self.root / 'bin' / command
            mock.write_text('''#!/bin/bash
set -eu
echo "${0##*/} $1" >> "$TEST_LOG"
case "${0##*/}:$1" in
  cosign:verify) [[ ${FAIL_VERIFY:-0} == 0 ]]; echo '{}' ;;
  skopeo:list-tags)
    [[ ${FAIL_REGISTRY:-0} == 0 ]]
    printf '%s' "${TEST_TAGS}"
    ;;
  skopeo:inspect) echo "$IMAGE_DIGEST" ;;
  skopeo:login) [[ $(cat) == fake-token ]] ;;
  skopeo:copy) [[ -z ${GHCR_TOKEN+x} ]] ;;
  *) exit 1 ;;
esac
''')
            mock.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.root / 'bin') + ':' + os.environ['PATH'],
                        RUNNER_TEMP=str(self.root), TEST_LOG=str(self.root / 'calls'),
                        RELEASE_TAG='v0.0.7-alpha', IMAGE_DIGEST='sha256:' + 'a' * 64,
                        EXPECTED_CURRENT='absent', GHCR_TOKEN='fake-token',
                        GITHUB_ACTOR='test', TEST_TAGS='{"Tags": []}')

    def run_script(self):
        return subprocess.run(['bash', str(SCRIPT)], cwd=self.root, env=self.env,
                              text=True, capture_output=True)

    def assert_no_publication(self):
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        calls = (self.root / 'calls').read_text()
        self.assertNotIn('skopeo login', calls)
        self.assertNotIn('skopeo copy', calls)

    def test_success_verifies_before_publication_and_cleans_auth(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / 'calls').read_text().splitlines(), [
            'cosign verify', 'cosign verify', 'skopeo list-tags', 'skopeo login',
            'skopeo copy', 'skopeo inspect', 'cosign verify'])
        self.assertEqual(list(self.root.glob('azurefin-promotion-auth.*')), [])

    def test_signature_failure(self):
        self.env['FAIL_VERIFY'] = '1'
        self.assert_no_publication()

    def test_registry_failure(self):
        self.env['FAIL_REGISTRY'] = '1'
        self.assert_no_publication()

    def test_malformed_registry_response(self):
        self.env['TEST_TAGS'] = 'not json'
        self.assert_no_publication()

    def test_existing_channel_requires_expected_digest(self):
        self.env['TEST_TAGS'] = '{"Tags": ["testing"]}'
        self.assert_no_publication()


if __name__ == '__main__':
    unittest.main()
