from pathlib import Path
import unittest

from vm_anaconda_kickstart import generate


class AnacondaTests(unittest.TestCase):
    def test_preserves_public_payload_and_post_scripts(self):
        public = Path(__file__).parents[1].joinpath('release-installer.ks').read_text()
        result = generate(public)
        original_posts = public.split('%post', 1)[1]
        self.assertIn('%post' + original_posts, result)
        self.assertIn('ostreecontainer --url=/run/install/repo/azurefin/base-oci --transport=oci', result)
        self.assertIn('ignoredisk --only-use=vda\n', result)
        self.assertIn('clearpart --all --initlabel --drives=vda\n', result)
        self.assertIn('AZUREFIN_NIX_ANACONDA_POST_COMPLETE', result)
        self.assertNotIn('clearpart', public)

    def test_missing_or_ambiguous_mode_refused(self):
        for public in ('', '\ntext\n', '\ngraphical\n\ngraphical\n'):
            with self.assertRaises(ValueError):
                generate(public)


if __name__ == '__main__':
    unittest.main()
