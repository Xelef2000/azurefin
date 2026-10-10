import unittest
from unittest.mock import patch
import json
from finalize_iso_release import main, removable_assets


class FinalizeTests(unittest.TestCase):
    def test_only_expected_assets_removed(self):
        assets = [{'name': n} for n in ('ISO-SHA256SUM', 'SHA256SUMS',
                  'BUILD-INFO.txt', 'iso-audit.log', 'azurefin-v0.0.1-alpha-aarch64.iso.part-000')]
        self.assertEqual(removable_assets(assets, 'v0.0.1-alpha'), assets[1:])
        with self.assertRaises(ValueError):
            removable_assets([{'name': 'unrelated.zip'}], 'v0.0.1-alpha')

    def run_case(self, mirrored_checksum=None, headers=None):
        checksum = 'a' * 64 + '  azurefin-v0.0.1-alpha-aarch64.iso\n'
        release = {'assets': [{'id': 1, 'name': 'ISO-SHA256SUM'},
                              {'id': 2, 'name': 'SHA256SUMS'}]}
        mutations = []
        def fake_gh(*args):
            if args == ('api', 'repos/owner/repo/releases/tags/v0.0.1-alpha'):
                return json.dumps(release)
            if 'Accept: application/octet-stream' in args:
                return checksum
            mutations.append(args)
            return ''
        with patch('finalize_iso_release.gh', side_effect=fake_gh), patch(
                'finalize_iso_release.subprocess.check_output', side_effect=[
                    mirrored_checksum if mirrored_checksum is not None else checksum,
                    headers if headers is not None else 'HTTP/2 200\ncontent-type: application/octet-stream\ncontent-length: 1234\n']):
            try:
                main('owner/repo', 'v0.0.1-alpha', 'azurefin')
            except ValueError:
                self.assertEqual(mutations, [])
                raise
        return mutations

    def test_link_before_delete(self):
        mutations = self.run_case()
        self.assertEqual(mutations[0][:2], ('release', 'edit'))
        self.assertEqual(mutations[1], ('api', '--method', 'DELETE', 'repos/owner/repo/releases/assets/2'))

    def test_mismatched_checksum_retains_assets(self):
        with self.assertRaises(ValueError):
            self.run_case(mirrored_checksum='wrong')

    def test_html_response_retains_assets(self):
        with self.assertRaises(ValueError):
            self.run_case(headers='HTTP/2 200\ncontent-type: text/html\ncontent-length: 1234\n')
