import unittest
import hashlib
from pathlib import Path
import tempfile

from audit_notice_coverage import coverage, verify_texts


class CoverageTests(unittest.TestCase):
    def inputs(self):
        return ({'runtime_outputs': ['out'], 'matches': [{'output': 'out', 'source': 'filtered'}]},
                {'sources': [{'source': 'parent', 'notices': [{'path': 'COPYING'}]}]})

    def test_parent_supplies_missing_notice(self):
        result = coverage(*self.inputs(), {'out': 'parent'})
        self.assertEqual(result['runtime_outputs'][0]['evidence'][0]['source'], 'parent')

    def test_missing_notices_fail(self):
        with self.assertRaises(ValueError):
            coverage(*self.inputs(), {})

    def test_stale_parent_mapping_fails(self):
        with self.assertRaises(ValueError):
            coverage(*self.inputs(), {'other-output': 'parent'})

    def test_parent_required_even_when_component_has_third_party_notice(self):
        runtime, notices = self.inputs()
        notices['sources'] = [{'source': 'filtered', 'notices': [{'path': 'third-party/LICENSE'}]}]
        with self.assertRaises(ValueError):
            coverage(runtime, notices, {'out': 'parent'})

    def test_notice_bytes_verified_and_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            digest = hashlib.sha256(b'terms').hexdigest()
            path = root / (digest + '.txt')
            notices = {'sources': [{'notices': [{'sha256': digest, 'bytes': 5}]}]}
            path.write_bytes(b'terms')
            verify_texts(notices, root)
            path.write_bytes(b'other')
            with self.assertRaises(ValueError):
                verify_texts(notices, root)
            path.unlink()
            target = root / 'target'
            target.write_bytes(b'terms')
            path.symlink_to(target)
            with self.assertRaises(ValueError):
                verify_texts(notices, root)


if __name__ == '__main__':
    unittest.main()
