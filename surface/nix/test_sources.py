import unittest

from inventory_sources import inventory, store_roots

OUT = '/nix/store/' + '0' * 32 + '-example-1'
SRC = '/nix/store/' + '1' * 32 + '-source'
PATCH = '/nix/store/' + '2' * 32 + '-fix.patch'


class SourceTests(unittest.TestCase):
    def inputs(self):
        return ({'store_outputs': [OUT], 'installer_sha256': 'test', 'source_revision': 'pin'},
                {'version': 4, 'derivations': {'example.drv': {
                    'outputs': {'out': {'path': OUT.removeprefix('/nix/store/')}},
                    'env': {'src': SRC, 'patches': PATCH},
                }}})

    def test_env_and_relative_output(self):
        result = inventory(*self.inputs())
        self.assertEqual(result['runtime_outputs'], [OUT])
        self.assertEqual(result['direct_source_roots'], [SRC, PATCH])
        self.assertFalse(result['complete_license_inventory'])

    def test_structured_and_nested_inputs(self):
        payload, graph = self.inputs()
        graph['derivations']['example.drv']['structuredAttrs'] = {
            'srcs': [SRC + '/subdir'], 'patches': [PATCH]}
        self.assertEqual(inventory(payload, graph)['direct_source_roots'], [SRC, PATCH])

    def test_missing_match_rejected(self):
        payload, graph = self.inputs()
        graph['derivations'] = {}
        with self.assertRaisesRegex(ValueError, 'Unmatched'):
            inventory(payload, graph)

    def test_unknown_schema_rejected(self):
        payload, graph = self.inputs()
        graph['version'] = 5
        with self.assertRaisesRegex(ValueError, 'schema'):
            inventory(payload, graph)

    def test_multiple_providers_retained(self):
        payload, graph = self.inputs()
        graph['derivations']['second.drv'] = graph['derivations']['example.drv']
        self.assertEqual(len(inventory(payload, graph)['matches']), 2)

    def test_store_roots(self):
        self.assertEqual(store_roots({'source': SRC, 'patches': [PATCH], 'flag': True}), {SRC, PATCH})


if __name__ == '__main__':
    unittest.main()
