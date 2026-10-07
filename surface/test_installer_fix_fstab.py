import pathlib
import tempfile
import tomllib
import unittest

from installer_fix_fstab import corrected_fstab, fix


FSTAB = """# Installer fixture
UUID=root / btrfs subvol=root,compress=zstd:1,ro 0 0
UUID=boot /boot ext4 defaults 1 2
UUID=efi /boot/efi vfat umask=0077 0 2
UUID=root /home btrfs subvol=home,compress=zstd:1 0 0
UUID=root /var btrfs subvol=var,compress=zstd:1 0 0
UUID=data /data ext4 defaults 0 2
"""
OPTIONS = [["root=UUID=root", "rootflags=subvol=root", "rd.luks.uuid=luks-test"]]


class FstabTests(unittest.TestCase):
    def test_encrypted_btrfs_preserves_other_mounts(self):
        output = corrected_fstab(FSTAB, OPTIONS, True)
        self.assertIn("# UUID=root / btrfs", output)
        self.assertLess(output.index(" /var btrfs"), output.index(" /var/home btrfs"))
        for line in FSTAB.splitlines():
            if any(mount in line for mount in (" /boot ", " /boot/efi ", " /data ", " /var ")):
                self.assertIn(line + "\n", output)
        self.assertIn("subvol=home,compress=zstd:1 0 0", output)
        self.assertEqual(output, corrected_fstab(output, OPTIONS, True))

    def test_plain_ext4_and_real_home(self):
        source = "UUID=root / ext4 defaults 0 1\nUUID=home /home ext4 defaults 0 2\n"
        output = corrected_fstab(source, [["root=UUID=root"]], False)
        self.assertIn("# UUID=root / ext4", output)
        self.assertIn("UUID=home /home ext4 defaults 0 2", output)

    def test_missing_or_wrong_boot_arguments_rejected(self):
        for options in ([], [["root=UUID=other", "rootflags=subvol=root"]],
                        [["root=UUID=root"]]):
            with self.subTest(options=options), self.assertRaises(ValueError):
                corrected_fstab(FSTAB, options, True)

    def test_ambiguous_or_malformed_entries_rejected(self):
        for source in (FSTAB + "UUID=other / ext4 defaults 0 0\n",
                       FSTAB + "UUID=other /var/home ext4 defaults 0 0\n",
                       FSTAB + "broken\n"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                corrected_fstab(source, OPTIONS, True)

    def test_install_backup_idempotence_and_crypttab_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for directory in ("etc", "usr/lib/ostree", "boot/loader/entries"):
                (root / directory).mkdir(parents=True)
            (root / "usr/lib/ostree/prepare-root.conf").write_text("[composefs]\nenabled=yes\n")
            (root / "boot/loader/entries/ostree.conf").write_text("options " + " ".join(OPTIONS[0]) + "\n")
            (root / "home").symlink_to("var/home")
            fstab = root / "etc/fstab"
            fstab.write_text(FSTAB)
            fstab.chmod(0o640)
            crypttab = root / "etc/crypttab"
            crypttab.write_text("root UUID=luks-test none luks\n")
            fix(root)
            fix(root)
            self.assertEqual((root / "etc/fstab.before-azurefin-composefs").read_text(), FSTAB)
            self.assertEqual(fstab.stat().st_mode & 0o777, 0o640)
            self.assertEqual(crypttab.read_text(), "root UUID=luks-test none luks\n")
            (root / "etc/ostree").mkdir()
            (root / "etc/ostree/prepare-root.conf").write_text("[composefs]\nenabled=no\n")
            with self.assertRaises(ValueError):
                fix(root)

    def test_hook_wired_into_both_payloads(self):
        repo = pathlib.Path(__file__).resolve().parent.parent
        config = tomllib.loads((repo / "iso/iso.toml").read_text())
        kickstart = config["customizations"]["installer"]["kickstart"]["contents"]
        self.assertIn("%post --erroronfail", kickstart)
        self.assertIn("python3 /usr/libexec/azurefin-installer-fix-fstab.py", kickstart)
        self.assertNotIn("--nochroot", kickstart)
        for name in ("Containerfile.romulus", "Containerfile.romulus-local"):
            self.assertIn("COPY surface/installer_fix_fstab.py /usr/libexec/azurefin-installer-fix-fstab.py",
                          (repo / name).read_text())
