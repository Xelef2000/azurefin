import unittest
from release_iso_grub import patch


CONFIG = """set timeout=60
search --set=root -l 'TEST-44'
menuentry 'Old entry' { linux /old }
submenu 'Troubleshooting' { menuentry 'Rescue' { linux /old } }
menuentry 'Display' --id romulus-preload-display {
 linux /images/pxeboot/vmlinuz inst.stage2=hd:LABEL=TEST-44 inst.ks=cdrom:/old.ks clk_ignore_unused pd_ignore_unused rd.driver.pre=msm,pmic-glink
 devicetree /images/dtbs/qcom/x1e80100-microsoft-romulus13.dtb
 initrd /images/pxeboot/initrd.img
}
set default=romulus-preload-display
"""


class ReleaseGrubTests(unittest.TestCase):
    def test_every_entry_uses_provisioning(self):
        result = patch(CONFIG)
        self.assertIn('inst.ks=hd:LABEL=TEST-44:/azurefin/install.ks', result)
        self.assertNotIn('cdrom:', result)
        self.assertEqual(result.count('menuentry '), 1)
        self.assertNotIn('submenu ', result)
        self.assertIn('rd.driver.pre=msm,pmic-glink', result)
        self.assertIn('clk_ignore_unused pd_ignore_unused', result)
        self.assertIn('set default=azurefin-install', result)
        self.assertEqual(patch(result), result)

    def test_unexpected_boot_configuration_rejected(self):
        for text in ('', CONFIG.replace('inst.stage2=hd:LABEL=TEST-44', ''),
                     CONFIG.replace('inst.ks=cdrom:/old.ks', 'inst.ks=a inst.ks=b'),
                     CONFIG.replace('rd.driver.pre=msm,pmic-glink', ''),
                     CONFIG.replace('pd_ignore_unused', 'rd.break=pre-udev')):
            with self.assertRaises(ValueError):
                patch(text)


if __name__ == '__main__':
    unittest.main()
