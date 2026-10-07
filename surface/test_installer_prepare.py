import tempfile
from pathlib import Path
import unittest
import os
import select
import subprocess
import sys
import tty
import io
from unittest.mock import patch
import json

from installer_prepare import kickstart, prepared_path, open_console, Tee, usb_partitions, msi_files, usb_msi_files
from installer_provision_grub import append_entry
from installer_prepare import bluetooth_address, prompt_bluetooth_address, confirm_download


class HandoffTests(unittest.TestCase):
    def test_confirmation_retries_blank_and_typos(self):
        with patch('builtins.input', side_effect=['', 'yse', ' YES ']) as ask:
            confirm_download()
            self.assertEqual(ask.call_count, 3)

    def test_confirmation_accepts_short_yes(self):
        with patch('builtins.input', return_value='y'):
            confirm_download()

    def test_confirmation_cancels_explicitly(self):
        for answer in ('no', 'n', 'q'):
            with patch('builtins.input', return_value=answer):
                with self.assertRaises(SystemExit):
                    confirm_download()

    def test_optional_bluetooth_address(self):
        self.assertIsNone(bluetooth_address("  "))
        self.assertEqual(bluetooth_address("12:34:56:78:9a:bc"), "12:34:56:78:9A:BC")
        for value in ("00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff", "12:34", "x\nreboot"):
            with self.assertRaises(ValueError):
                bluetooth_address(value)

    def test_bluetooth_prompt_retries_invalid_input(self):
        with patch('builtins.input', side_effect=['bad', '12:34:56:78:9a:bc']):
            self.assertEqual(prompt_bluetooth_address(), '12:34:56:78:9A:BC')

    def test_bluetooth_written_in_target_post_only(self):
        path = '/run/azurefin-work/runs/azurefin-provision.1234/container'
        plain = kickstart(path, 'sda')
        self.assertNotIn('--bluetooth-address', plain)
        configured = kickstart(path, 'sda', bluetooth_mac='12:34:56:78:9a:bc')
        self.assertIn('azurefin-extract-firmware --bluetooth-address 12:34:56:78:9A:BC\n', configured)
        self.assertGreater(configured.index('--bluetooth-address'), configured.index('%post '))

    def test_existing_workspace_is_not_remounted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "firmware").mkdir()
            msi = root / "firmware/SurfaceLaptop7.msi"
            msi.write_text("test")
            listing = {"blockdevices": [{"name": "/dev/sda", "type": "disk", "tran": "usb",
                "children": [{"name": "/dev/sda3", "type": "part", "fstype": "ext4"}]}]}
            with patch("installer_prepare.subprocess.check_output", return_value=json.dumps(listing)), \
                    patch("installer_prepare.subprocess.run") as run:
                with usb_msi_files(root, "sda") as files:
                    self.assertEqual(files, [(msi, "sda")])
                run.assert_not_called()

    def test_msi_on_installer_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "firmware").mkdir()
            msi = root / "firmware/SurfaceLaptop7.MSI"
            msi.write_text("test")
            other = root / "other.msi"
            other.write_text("test")
            (root / "shortcut.msi").symlink_to(msi)
            self.assertEqual(set(msi_files(root)), {msi, other})

    def test_same_source_disk_is_excluded_once(self):
        text = kickstart("/run/azurefin-work/runs/azurefin-provision.1234/container", "sda", "sda")
        self.assertIn("ignoredisk --drives=sda\n", text)
        self.assertNotIn("sda,sda", text)

    def test_console_output_and_errors_are_logged(self):
        console, anaconda, persistent = io.StringIO(), io.StringIO(), io.StringIO()
        output = Tee(console, anaconda, persistent)
        print("preparation failed", file=output, flush=True)
        self.assertEqual(console.getvalue(), anaconda.getvalue())
        self.assertEqual(console.getvalue(), persistent.getvalue())
        self.assertIn("preparation failed", persistent.getvalue())

    def test_only_plain_usb_filesystems_are_scanned(self):
        devices = [
            {"name": "/dev/nvme0n1", "type": "disk", "tran": "nvme", "children": [
                {"name": "/dev/nvme0n1p1", "type": "part", "fstype": "ext4"}]},
            {"name": "/dev/sdb", "type": "disk", "tran": "usb", "children": [
                {"name": "/dev/sdb1", "type": "part", "fstype": "exfat"},
                {"name": "/dev/sdb2", "type": "part", "fstype": "crypto_LUKS"}]},
        ]
        self.assertEqual(list(usb_partitions(devices)), [("/dev/sdb1", "sdb")])

    def test_msi_source_disk_is_also_excluded(self):
        text = kickstart("/run/azurefin-work/runs/azurefin-provision.1234/container", "sda", "sdb")
        self.assertIn("ignoredisk --drives=sda,sdb\n", text)

    def test_console_on_real_nonseekable_pty(self):
        master, slave = os.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        tty.setraw(slave)
        reader, writer = open_console(os.ttyname(slave))
        self.addCleanup(reader.close)
        self.addCleanup(writer.close)
        self.assertFalse(reader.seekable())
        self.assertFalse(writer.seekable())
        writer.write("Consent?\n")
        self.assertTrue(select.select([master], [], [], 2)[0])
        self.assertEqual(os.read(master, 100), b"Consent?\n")
        os.write(master, b"yes\n")
        self.assertTrue(select.select([slave], [], [], 2)[0])
        self.assertEqual(reader.readline(), "yes\n")
        # NetworkManager receives the read descriptor, not the output stream.
        os.write(master, b"wifi\n")
        subprocess.run([sys.executable, "-c",
                        "import sys; print(sys.stdin.readline().strip())"],
                       stdin=reader, stdout=writer, stderr=writer,
                       check=True, timeout=5)
        self.assertTrue(select.select([master], [], [], 2)[0])
        self.assertEqual(os.read(master, 100), b"wifi\n")

    def test_grub_preserves_old_entries_and_default(self):
        old = "menuentry 'Install Fedora Linux 44' {\n  linux /vmlinuz inst.stage2=hd:LABEL=AZUREDATA inst.ks=hd:LABEL=AZUREDATA:/osbuild.ks\n  initrd /initrd\n}\nset default=0\n"
        new = append_entry(old)
        self.assertTrue(new.startswith(old))
        self.assertIn("inst.ks=hd:LABEL=AZUREFIN_WORK:/installer-provision.ks", new)
        self.assertEqual(new.count("set default="), 1)
        with self.assertRaises(ValueError):
            append_entry(new)

    def test_excludes_workspace_disk_and_uses_prepared_payload(self):
        text = kickstart("/run/azurefin-work/runs/azurefin-provision.1234/container", "sdb")
        self.assertIn("ignoredisk --drives=sdb\n", text)
        self.assertIn("--transport=oci", text)
        self.assertIn("installer-fix-fstab.py", text)
        self.assertNotIn("clearpart", text)
        self.assertNotIn("autopart", text)

    def test_rejects_path_or_disk_injection(self):
        for disk in ("nvme0n1", "sda\nclearpart --all", "sda,sdb", "../sda"):
            with self.assertRaises(ValueError):
                kickstart("/run/azurefin-work/runs/azurefin-provision.1234/container", disk)
        for path in ("/tmp/container", "/run/azurefin-work/runs/../container", "x\nautopart"):
            with self.assertRaises(ValueError):
                kickstart(path, "sda")

    def test_requires_matching_ready_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory)
            work = runs / "azurefin-provision.1234"
            payload = work / "container"
            payload.mkdir(parents=True)
            (work / "READY").write_text(str(payload) + "\n")
            for name in ("index.json", "oci-layout"):
                (payload / name).write_text("{}")
            line = "PAYLOAD_READY: " + str(payload) + "\n"
            self.assertEqual(prepared_path(line, runs), str(payload))
            (work / "READY").write_text("/wrong/path\n")
            with self.assertRaises(ValueError):
                prepared_path(line, runs)

    def test_bootstrap_fails_closed_before_include(self):
        text = Path(__file__).with_name("installer-provision.ks").read_text()
        self.assertIn("%pre --erroronfail", text)
        self.assertNotIn("%pre-install", text)
        self.assertLess(text.index("installer_prepare.py"), text.index("%include"))


if __name__ == "__main__":
    unittest.main()
