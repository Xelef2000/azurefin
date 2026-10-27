"""Release wiring checks: no firmware or machine-specific settings in the image."""
from pathlib import Path
import unittest


class FirmwareStoreBuildTests(unittest.TestCase):
    def setUp(self):
        self.surface = Path(__file__).parent
        self.containerfile = (self.surface.parent / 'Containerfile.romulus').read_text()

    def test_base_includes_loader_before_initramfs_generation(self):
        base = self.containerfile.split('FROM packages AS base-image\n', 1)[1]
        self.assertIn('COPY surface/dracut/91azurefin-firmware ', base)
        self.assertIn('COPY surface/firmware_bundle.py surface/firmware_store_probe.py ', base)
        self.assertLess(base.index('20-firmware-store.sh'),
                        base.index('21-installer-firmware-free.sh installed'))
        self.assertIn('systemctl mask bootc-fetch-apply-updates.timer', base)

    def test_module_includes_manifest_and_runs_before_coldplug(self):
        module = (self.surface / 'dracut/91azurefin-firmware/module-setup.sh').read_text()
        self.assertIn('/usr/share/azurefin/boot-firmware.sha256', module)
        self.assertIn('inst_hook pre-udev 00', module)
        self.assertIn('instmods nvme phy_qcom_qmp_pcie ext4', module)

    def test_build_only_emits_manifest(self):
        script = (self.surface / 'build/20-firmware-store.sh').read_text()
        self.assertIn('--emit-manifest', script)
        for forbidden in ('--source ', '--store ', 'azurefin.boot_uuid=', 'bootc switch',
                          'systemctl unmask', 'curl ', 'wget '):
            self.assertNotIn(forbidden, script)


if __name__ == '__main__':
    unittest.main()
