"""Safety defaults for upstream scheduled and manual updates."""
import configparser
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent


class UpdaterTests(unittest.TestCase):
    def test_system_and_apps_enabled_with_hardware_checks(self):
        config = json.loads((ROOT / "build/uupd/config.json").read_text())
        self.assertFalse(config["modules"]["system"]["disable"])
        self.assertTrue(config["checks"]["hardware"]["enable"])
        self.assertTrue(config["modules"]["distrobox"]["disable"])
        self.assertFalse(config["modules"]["flatpak"]["disable"])
        self.assertFalse(config["modules"]["brew"]["disable"])

    def test_launcher_uses_standard_manual_entrypoint_without_reboot(self):
        desktop = configparser.ConfigParser(interpolation=None)
        desktop.read(ROOT / "build/uupd/system-update.desktop")
        command = desktop["Desktop Entry"]["Exec"]
        self.assertEqual(command, '/usr/bin/ujust update')
        self.assertNotIn("--apply", command.split())
        self.assertEqual(desktop["Desktop Entry"]["Name"], 'System Update')

    def test_manual_and_scheduled_paths_share_provisioning_lock_and_guard(self):
        for name in ('update.just', '20-azurefin-safety.conf'):
            contents = (ROOT / 'build/uupd' / name).read_text()
            self.assertIn('flock --nonblock /var/lib/azurefin/firmware-store.lock', contents)
            self.assertIn('system_update_preflight.py &&', contents)
            self.assertNotIn('--apply', contents)
        safety = (ROOT / 'build/uupd/20-azurefin-safety.conf').read_text()
        self.assertIn('ConditionACPower=true', safety)
        self.assertIn('ConditionKernelCommandLine=!azurefin.live=1', safety)
        self.assertIn('ConditionKernelCommandLine=!rd.live.image', safety)
        self.assertIn('--hw-check', safety)
        timer = (ROOT / 'build/uupd/20-azurefin-schedule.conf').read_text()
        self.assertIn('OnCalendar=\nOnCalendar=*-*-* 00,06,12,18:00:00', timer)
        self.assertIn('Persistent=true', timer)
        self.assertIn('RandomizedDelaySec=10m', timer)
        self.assertIn('ConditionKernelCommandLine=!azurefin.live=1', timer)
        self.assertIn('ConditionKernelCommandLine=!rd.live.image', timer)

    def test_single_scheduler_and_package_pin(self):
        script = (ROOT / "build/17-uupd.sh").read_text()
        self.assertIn("systemctl unmask uupd.timer", script)
        self.assertIn("systemctl enable uupd.timer", script)
        self.assertIn("systemctl disable brew-update.timer brew-upgrade.timer", script)
        self.assertNotIn("systemctl disable brew-setup.service", script)
        self.assertNotIn("systemctl mask uupd.timer", script)
        self.assertIn("uupd-1.5.2-1.fc44.aarch64", script)
        self.assertLess(script.index("dnf5 copr disable"), script.index("dnf5 install"))
        self.assertNotIn("gnome-software", script)

    def test_build_wires_updater_and_blocks_unguarded_scheduler(self):
        containerfile = (ROOT.parent / "Containerfile.romulus").read_text()
        self.assertIn("bash /ctx/build/17-uupd.sh", containerfile)
        self.assertLess(containerfile.index('bash /ctx/build/15-homebrew.sh'),
                        containerfile.index('bash /ctx/build/17-uupd.sh'))
        self.assertIn('systemctl mask bootc-fetch-apply-updates.timer bootc-fetch-apply-updates.service',
                      containerfile)

    def test_bazaar_preinstall_definition(self):
        manifest = configparser.ConfigParser()
        manifest.read(ROOT / "build/bazaar/bazaar.preinstall")
        app = manifest["Flatpak Preinstall io.github.kolunmi.Bazaar"]
        self.assertEqual(app["Branch"], "stable")
        # A newly added Flathub remote has no collection ID in its config.
        # Restricting it here silently prevents Flatpak from selecting it.
        self.assertNotIn("CollectionID", app)
        self.assertFalse(app.getboolean("IsRuntime"))

    def test_bazaar_offline_retry_and_live_exclusion(self):
        service = (ROOT / "build/bazaar/azurefin-flatpak-preinstall.service").read_text()
        timer = (ROOT / "build/bazaar/azurefin-flatpak-preinstall.timer").read_text()
        self.assertNotIn("RemainAfterExit=true", service)
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

    def test_bazaar_replaces_gnome_software_without_dependency_cleanup(self):
        script = (ROOT / "build/18-bazaar.sh").read_text()
        self.assertIn("dnf5 remove -y --setopt=clean_requirements_on_remove=False gnome-software", script)
        self.assertIn("if rpm -q gnome-software", script)
        self.assertIn("flatpak preinstall --help", script)

    def test_generated_appstream_cache_is_cleaned_inside_build_only(self):
        script = (ROOT / "build/29-clean-build-state.sh").read_text()
        self.assertIn("Refusing build-state cleanup outside a container", script)
        self.assertIn("/var/cache/swcatalog/cache/C-local-metainfo.xb", script)
        self.assertIn("/var/cache/swcatalog/cache/C-os-catalog.xb", script)


if __name__ == "__main__":
    unittest.main()
