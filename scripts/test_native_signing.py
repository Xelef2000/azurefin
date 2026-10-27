"""Exercise signing orchestration offline with a fake cosign executable."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parent / 'sign-native-ota.sh'


class SigningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ('bin', 'surface', 'release-metadata', 'temp'):
            (self.root / name).mkdir()
        (self.root / 'surface/ota-signing.pub').write_text('test-public-key\n')
        mock = self.root / 'bin/cosign'
        mock.write_text('''#!/bin/bash
set -eu
echo "$1" >> "$TEST_LOG"
case "$1" in
  public-key) echo "${TEST_PUBLIC_KEY:-test-public-key}" ;;
  login)
    [[ ${TEST_LOGIN_FAIL:-0} == 0 ]] || exit 1
    [[ $(cat) == test-token ]]
    printf '{}' > "$DOCKER_CONFIG/config.json"
    ;;
  sign|verify)
    [[ -s "$DOCKER_CONFIG/config.json" ]]
    [[ -z ${GHCR_TOKEN+x} ]]
    printf '{}'
    ;;
  *) exit 1 ;;
esac
''')
        mock.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.root / 'bin') + ':' + os.environ['PATH'],
                        TEST_LOG=str(self.root / 'calls'), RUNNER_TEMP=str(self.root / 'temp'),
                        RELEASE_TAG='v0.0.7-alpha', REGISTRY_OWNER='Xelef2000',
                        GHCR_TOKEN='test-token', AZUREFIN_OTA_SIGNING_KEY='test-key',
                        COSIGN_PASSWORD='test-password')

    def run_script(self, reference=None):
        return subprocess.run(['bash', str(SCRIPT), reference or
                               'ghcr.io/xelef2000/azurefin@sha256:' + 'a' * 64],
                              cwd=self.root, env=self.env, capture_output=True, text=True)

    def test_independent_login_and_cleanup(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / 'calls').read_text().splitlines(),
                         ['public-key', 'login', 'sign', 'verify'])
        self.assertEqual(list((self.root / 'temp').iterdir()), [])

    def test_login_failure_never_signs(self):
        self.env['TEST_LOGIN_FAIL'] = '1'
        self.assertNotEqual(self.run_script().returncode, 0)
        self.assertEqual((self.root / 'calls').read_text().splitlines(), ['public-key', 'login'])
        self.assertEqual(list((self.root / 'temp').iterdir()), [])

    def test_wrong_key_never_logs_in(self):
        self.env['TEST_PUBLIC_KEY'] = 'wrong-key'
        self.assertNotEqual(self.run_script().returncode, 0)
        self.assertEqual((self.root / 'calls').read_text().splitlines(), ['public-key'])

    def test_mutable_tag_rejected(self):
        self.assertNotEqual(self.run_script('ghcr.io/xelef2000/azurefin:latest').returncode, 0)
        self.assertFalse((self.root / 'calls').exists())


if __name__ == '__main__':
    unittest.main()
