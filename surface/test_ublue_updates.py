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


if __name__ == "__main__":
    unittest.main()
