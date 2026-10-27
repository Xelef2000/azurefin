import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import update


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.config = json.dumps({'architecture': 'arm64', 'os': 'linux'}).encode()
        self.config_digest = 'sha256:' + hashlib.sha256(self.config).hexdigest()
        self.manifest = {'config': {'digest': self.config_digest}, 'layers': []}
        self.raw = json.dumps(self.manifest).encode()
        self.digest = 'sha256:' + hashlib.sha256(self.raw).hexdigest()
        self.reference = update.REPOSITORY + '@' + self.digest

    def test_release_validation(self):
        for value in ('v0.0.4-alpha', 'v1.2.3'):
            self.assertEqual(update.release(value), value)
        for value in ('main', 'latest', '../v1.0.0', 'v1.0.0;id', 'v1.0.0\n'):
            with self.assertRaises(argparse.ArgumentTypeError):
                update.release(value)

    def test_exact_identity_and_signed_claims(self):
        with patch.object(update.subprocess, 'check_output', return_value=self.raw), \
                patch.object(update.subprocess, 'run') as run:
            reference, manifest = update.verified_manifest('v0.0.4-alpha')
        self.assertEqual(reference, self.reference)
        self.assertEqual(manifest, self.manifest)
        run.assert_called_once_with([
            'cosign', 'verify', '--certificate-identity',
            update.WORKFLOW + '@refs/tags/v0.0.4-alpha',
            '--certificate-oidc-issuer', update.ISSUER,
            '-a', 'release=v0.0.4-alpha', '-a', 'component=base', self.reference], check=True)

    def test_unsigned_wrong_identity_and_tampered_signatures_fail_closed(self):
        with patch.object(update.subprocess, 'check_output', return_value=self.raw), \
                patch.object(update.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'cosign')):
            with self.assertRaises(subprocess.CalledProcessError):
                update.verified_manifest('v0.0.4-alpha')

    def test_index_is_rejected(self):
        with patch.object(update.subprocess, 'check_output', return_value=b'{"manifests": []}'), \
                patch.object(update.subprocess, 'run') as run:
            with self.assertRaises(RuntimeError):
                update.verified_manifest('v0.0.4-alpha')
            run.assert_not_called()

    def download(self, root, digest=None, config=None):
        base = root / 'base-oci'
        blobs = base / 'blobs/sha256'
        blobs.mkdir(parents=True)
        (base / 'index.json').write_text(json.dumps({'manifests': [{'digest': digest or self.digest}]}))
        (blobs / self.config_digest.split(':')[1]).write_bytes(self.config if config is None else config)

    def test_copy_uses_verified_digest_not_mutable_tag(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(update.subprocess, 'run') as run:
            root = Path(directory)
            self.download(root)
            self.assertEqual(update.fetch(root, self.reference, self.manifest), self.config_digest)
            run.assert_called_once_with(['skopeo', 'copy', '--preserve-digests',
                                         'docker://' + self.reference, f'oci:{root}/base-oci'], check=True)

    def test_changed_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(update.subprocess, 'run'):
            root = Path(directory)
            self.download(root, digest='sha256:' + '0' * 64)
            with self.assertRaisesRegex(RuntimeError, 'manifest differs'):
                update.fetch(root, self.reference, self.manifest)

    def test_changed_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(update.subprocess, 'run'):
            root = Path(directory)
            self.download(root, config=b'{}')
            with self.assertRaisesRegex(RuntimeError, 'config digest mismatch'):
                update.fetch(root, self.reference, self.manifest)

    def test_verification_failure_never_exports_or_stages(self):
        with patch('sys.argv', ['azurefin-update', '--release', 'v0.0.4-alpha', '--check']), \
                patch.object(update.shutil, 'which', return_value='/usr/bin/tool'), \
                patch.object(update, 'verified_manifest', side_effect=RuntimeError('bad signature')), \
                patch.object(update, 'fetch') as fetch, \
                patch.object(update.firmware, 'prepare') as prepare:
            with self.assertRaises(RuntimeError):
                update.main()
            fetch.assert_not_called()
            prepare.assert_not_called()

    def test_prepare_only_and_explicit_staging(self):
        for stage in (False, True):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                payload = root / 'azurefin-provision.test/container'
                payload.mkdir(parents=True)
                args = ['azurefin-update', '--release', 'v0.0.4-alpha', '--download']
                if stage:
                    args.append('--stage')
                old_umask = update.os.umask(0o022)
                try:
                    with patch('sys.argv', args), patch.object(update, 'RUNS', root), \
                            patch.object(update.os, 'geteuid', return_value=0), \
                            patch.object(update.shutil, 'which', return_value='/usr/bin/tool'), \
                            patch.object(update.shutil, 'disk_usage') as usage, \
                            patch.object(update, 'verified_manifest', return_value=(self.reference, self.manifest)), \
                            patch.object(update, 'fetch', return_value=self.config_digest), \
                            patch.object(update, 'export_support'), \
                            patch.object(update.firmware, 'prepare', return_value=payload), \
                            patch.object(update.subprocess, 'run') as run:
                        usage.return_value.free = 100 * 1024**3
                        update.main()
                        commands = [call.args[0] for call in run.call_args_list]
                        expected = [['bootc', 'status']]
                        if stage:
                            expected.append(['bootc', 'switch', '--transport', 'oci', str(payload)])
                        self.assertEqual(commands, expected)
                        receipt = json.loads((payload.parent / 'verified-update.json').read_text())
                        self.assertEqual(receipt['verified_base'], self.reference)
                finally:
                    update.os.umask(old_umask)


if __name__ == '__main__':
    unittest.main()
