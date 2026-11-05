import unittest

from collect_sources import flake_paths, native_paths

SRC = '/nix/store/' + '1' * 32 + '-source'
PATCH = '/nix/store/' + '2' * 32 + '-fix.patch'


class CollectionTests(unittest.TestCase):
    def test_nested_flakes(self):
        self.assertEqual(flake_paths({'path': SRC, 'inputs': {'child': {'path': PATCH}}}), {SRC, PATCH})

    def test_non_store_path_rejected(self):
        with self.assertRaises(ValueError):
            flake_paths({'path': '/home/person/private'})

    def test_native_plan_matches_graph(self):
        graph = {'derivations': {'native.drv': {'env': {'src': SRC, 'patches': PATCH}}}}
        plan = [{'derivation': 'native.drv', 'source': SRC, 'patches': PATCH}]
        self.assertEqual(native_paths(plan, graph), {SRC, PATCH})
        plan[0]['source'] = PATCH
        with self.assertRaises(ValueError):
            native_paths(plan, graph)


if __name__ == '__main__':
    unittest.main()
