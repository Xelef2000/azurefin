import unittest
from release_iso_grub import patch


class ReleaseGrubTests(unittest.TestCase):
    def test_every_entry_uses_provisioning(self):
        text = 'linux /images/pxeboot/vmlinuz inst.ks=hd:LABEL=OLD:/osbuild.ks\n'
        text += '  linuxefi /images/pxeboot/vmlinuz inst.ks=cdrom:/old.ks rd.break=pre-udev\n'
        result = patch(text)
        self.assertEqual(result.count('inst.ks=cdrom:/azurefin/install.ks'), 2)
        self.assertEqual(patch(result), result)

    def test_unexpected_boot_configuration_rejected(self):
        for text in ('', 'linux /vmlinuz\n', 'linux /vmlinuz inst.ks=a inst.ks=b\n'):
            with self.assertRaises(ValueError):
                patch(text)


if __name__ == '__main__':
    unittest.main()
