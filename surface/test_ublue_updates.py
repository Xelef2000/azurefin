"""Safety defaults for the initial upstream-updater preview."""
import configparser
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent


class UpdaterPreviewTests(unittest.TestCase):
    def test_system_and_distrobox_are_disabled(self):
        config = json.loads((ROOT / "build/uupd/config.json").read_text())
        self.assertTrue(config["modules"]["system"]["disable"])
        self.assertTrue(config["modules"]["distrobox"]["disable"])
        self.assertFalse(config["modules"]["flatpak"]["disable"])
        self.assertFalse(config["modules"]["brew"]["disable"])

    def test_launcher_does_not_stage_or_reboot(self):
        desktop = configparser.ConfigParser(interpolation=None)
        desktop.read(ROOT / "build/uupd/application-updates.desktop")
        command = desktop["Desktop Entry"]["Exec"]
        self.assertIn("--disable-module-system", command.split())
        self.assertNotIn("--apply", command.split())
        self.assertIn("Preview", desktop["Desktop Entry"]["Name"])

    def test_timer_mask_and_package_pin(self):
        script = (ROOT / "build/17-uupd.sh").read_text()
        self.assertIn("systemctl mask uupd.timer", script)
        self.assertIn("uupd-1.5.0-1.fc44.aarch64", script)
        self.assertLess(script.index("dnf5 copr disable"), script.index("dnf5 install"))
        self.assertNotIn("gnome-software", script)

    def test_build_wires_preview(self):
        containerfile = (ROOT.parent / "Containerfile.romulus").read_text()
        self.assertIn("bash /ctx/build/17-uupd.sh", containerfile)

    def test_bazaar_preinstall_definition(self):
        manifest = configparser.ConfigParser()
        manifest.read(ROOT / "build/bazaar/bazaar.preinstall")
        app = manifest["Flatpak Preinstall io.github.kolunmi.Bazaar"]
        self.assertEqual(app["Branch"], "stable")
        self.assertEqual(app["CollectionID"], "org.flathub.Stable")
        self.assertFalse(app.getboolean("IsRuntime"))

    def test_bazaar_offline_retry_and_live_exclusion(self):
        service = (ROOT / "build/bazaar/azurefin-flatpak-preinstall.service").read_text()
        timer = (ROOT / "build/bazaar/azurefin-flatpak-preinstall.timer").read_text()
        self.assertIn("RemainAfterExit=true", service)
        self.assertIn("TimeoutStartSec=30min", service)
        self.assertIn("OnUnitInactiveSec=15min", timer)
        self.assertIn("OnBootSec=2min", timer)
        self.assertNotIn("WantedBy=multi-user.target", service)
        for unit in (service, timer):
            self.assertIn("ConditionKernelCommandLine=!rd.live.image", unit)
            self.assertIn("ConditionKernelCommandLine=!azurefin.live=1", unit)
        self.assertIn("--if-not-exists flathub https://flathub.org/", service)
        self.assertNotIn("--no-gpg-verify", service)

    def test_bazaar_build_does_not_download_applications(self):
        script = (ROOT / "build/18-bazaar.sh").read_text()
        self.assertIn("systemctl enable azurefin-flatpak-preinstall.timer", script)
        self.assertNotIn("flatpak install", script)
        self.assertNotIn("remote-add", script)
        self.assertIn("bash /ctx/build/18-bazaar.sh",
                      (ROOT.parent / "Containerfile.romulus").read_text())


if __name__ == "__main__":
    unittest.main()
