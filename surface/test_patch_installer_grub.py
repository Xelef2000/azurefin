import unittest
from pathlib import Path
import hashlib
import re
import shutil
import subprocess
import tempfile

from patch_installer_grub import DTB_PATH, EARLY_DISPLAY_DRIVERS, patch_config


class GrubConfigTests(unittest.TestCase):
    def test_normal_entry(self):
        source = ("menuentry 'Install' {\n"
                  "  linux /images/pxeboot/vmlinuz inst.text inst.ks=hd:LABEL=TEST:/osbuild.ks\n"
                  "  initrd /images/pxeboot/initrd.img\n}\n")
        result = patch_config(source)
        self.assertNotIn("inst.text", result)
        self.assertIn("inst.graphical", result)
        self.assertIn("inst.ks=hd:LABEL=TEST:/osbuild.ks", result)
        self.assertIn(f"  devicetree {DTB_PATH}\n  initrd", result)
        self.assertIn("clk_ignore_unused pd_ignore_unused", result)

    def test_rescue_remains_rescue(self):
        result = patch_config("linux /images/pxeboot/vmlinuz inst.rescue inst.text\n")
        self.assertIn("inst.rescue", result)
        self.assertNotIn("inst.graphical", result)

    def test_diagnostic_entries_preserve_normal_boot(self):
        source = ("menuentry 'Install' {\n"
                  " linux /images/pxeboot/vmlinuz quiet inst.text inst.ks=hd:LABEL=TEST:/osbuild.ks\n"
                  " initrd /images/pxeboot/initrd.img\n}\n")
        result = patch_config(source, diagnostic=True)
        normal, diagnostic = result.split("menuentry 'Surface diagnostic:", 1)
        self.assertIn("quiet", normal)
        self.assertNotIn("quiet", diagnostic)
        self.assertEqual(diagnostic.count("panic=0"), 3)
        self.assertEqual(diagnostic.count("consoleblank=0"), 3)
        self.assertEqual(diagnostic.count("systemd.log_level=info"), 3)
        self.assertNotIn("rd.debug", diagnostic)
        self.assertNotIn("systemd.log_level=debug", diagnostic)
        self.assertEqual(diagnostic.count("rd.break=pre-udev"), 1)
        self.assertEqual(diagnostic.count("inst.ks=hd:LABEL=TEST:/osbuild.ks"), 3)
        self.assertEqual(diagnostic.count("rd.driver.pre="), 1)
        self.assertIn("rd.driver.pre=" + ",".join(EARLY_DISPLAY_DRIVERS), diagnostic)
        preload = diagnostic.split("--id romulus-preload-display", 1)[1]
        self.assertNotIn("rd.break=", preload)
        self.assertNotIn("battery_check=0", result)
        self.assertIn("set default=romulus-preload-display", result)

    def test_diagnostic_requires_expected_initrd(self):
        with self.assertRaises(ValueError):
            patch_config("linux /images/pxeboot/vmlinuz\n", diagnostic=True)

    def test_rejects_unexpected_configurations(self):
        for source in ("", "linux /different/kernel\n", "devicetree /existing.dtb\n"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                patch_config(source)


@unittest.skipUnless(all(shutil.which(tool) for tool in (
    "xorriso", "mformat", "mmd", "mcopy", "grub2-script-check",
    "implantisomd5", "checkisomd5", "uuidgen", "mlabel", "cpio", "mdir",
    "mksquashfs", "unsquashfs")), "ISO tools are not installed")
class IsoPreparationTests(unittest.TestCase):
    def test_new_iso_has_patched_config_and_efi_partition(self):
        self.check_prepared_iso(capture=False)

    def test_capture_iso_has_matching_media_token_and_overlay(self):
        self.check_prepared_iso(capture=True)

    def check_prepared_iso(self, capture):
        def run(*args):
            result = subprocess.run(args, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return result.stdout + result.stderr

        with tempfile.TemporaryDirectory(prefix="romulus-iso-test-") as name:
            root = Path(name)
            tree = root / "tree"
            (tree / "EFI/BOOT").mkdir(parents=True)
            (tree / "images/pxeboot").mkdir(parents=True)
            cfg = tree / "EFI/BOOT/grub.cfg"
            cfg.write_text("menuentry 'Test' {\n"
                           " linux /images/pxeboot/vmlinuz inst.text\n"
                           " initrd /images/pxeboot/initrd.img\n}\n")
            (tree / "osbuild.ks").write_text(
                "%include /run/install/repo/osbuild-base.ks\ngraphical\n")
            (tree / "osbuild-base.ks").write_text("# Interactive test fixture\n")
            # Fixtures validate ISO packaging, not executable EFI/kernel code.
            (tree / "images/pxeboot/vmlinuz").write_bytes(b"kernel fixture")
            (tree / "images/pxeboot/initrd.img").write_bytes(b"initrd fixture")
            dtb = root / "romulus13.dtb"
            dtb.write_bytes(bytes.fromhex("d00dfeed") + b"fixture")
            efi = tree / "images/efiboot.img"
            run("mformat", "-C", "-i", str(efi), "-T", "40960", "::")
            run("mmd", "-i", str(efi), "::/EFI", "::/EFI/BOOT")
            run("mcopy", "-i", str(efi), str(cfg), "::/EFI/BOOT/grub.cfg")
            original = root / "source.iso"
            run("xorriso", "-as", "mkisofs", "-R", "-J", "-V", "ROMULUS_TEST",
                "-e", "images/efiboot.img", "-no-emul-boot",
                "-o", str(original), str(tree))
            output = root / "prepared.iso"
            with original.open("rb") as image:
                source_hash = hashlib.file_digest(image, "sha256").hexdigest()
            script = Path(__file__).with_name("40-prepare-romulus-iso.sh")
            option = "--capture-logs" if capture else "--diagnostic"
            prefix = []
            if capture:
                squash_source = root / "squash-source"
                squash_source.mkdir()
                (squash_source / "fixture").write_text("XZ installer replacement\n")
                replacement = root / "install-xz.img"
                run("mksquashfs", str(squash_source), str(replacement),
                    "-comp", "xz", "-processors", "1", "-no-progress", "-noappend")
                prefix = ["env", f"ROMULUS_INSTALLER_SQUASHFS={replacement}"]
            run(*prefix, "bash", str(script), str(original), str(dtb), str(output), option)
            report = run("xorriso", "-indev", str(output), "-report_system_area", "plain")
            self.assertIn("GPT", report)
            self.assertIn("28732ac11ff8d211ba4b00a0c93ec93b", report.lower())
            partition = re.search(r"GPT start and size\s*:\s*2\s+(\d+)\s+(\d+)", report)
            self.assertIsNotNone(partition, report)
            start, size = map(int, partition.groups())
            appended_efi = root / "appended-efi.img"
            with output.open("rb") as image:
                image.seek(start * 512)
                appended_efi.write_bytes(image.read(size * 512))
            usb_cfg = root / "usb.cfg"
            run("mcopy", "-i", str(appended_efi), "::/EFI/BOOT/grub.cfg", str(usb_cfg))
            extracted = root / "verified.cfg"
            run("xorriso", "-osirrox", "on", "-indev", str(output),
                "-extract", "/EFI/BOOT/grub.cfg", str(extracted))
            self.assertIn(f"devicetree {DTB_PATH}", extracted.read_text())
            self.assertIn("set default=romulus-preload-display", extracted.read_text())
            self.assertEqual(usb_cfg.read_bytes(), extracted.read_bytes())
            if capture:
                extracted_squash = root / "verified-install.img"
                run("xorriso", "-osirrox", "on", "-indev", str(output),
                    "-extract", "/images/install.img", str(extracted_squash))
                self.assertEqual(extracted_squash.read_bytes(), replacement.read_bytes())
                self.assertIn("/images/romulus-capture.cpio", extracted.read_text())
                token = root / "media-token"
                run("mcopy", "-i", str(appended_efi), "::/romulus-capture-token", str(token))
                archive = root / "capture.cpio"
                run("xorriso", "-osirrox", "on", "-indev", str(output),
                    "-extract", "/images/romulus-capture.cpio", str(archive))
                with archive.open("rb") as data:
                    result = subprocess.run(
                        ["cpio", "-i", "--to-stdout", "etc/romulus-capture/token"],
                        stdin=data, capture_output=True, check=True)
                self.assertEqual(result.stdout, token.read_bytes())
                with archive.open("rb") as data:
                    result = subprocess.run(
                        ["cpio", "-i", "--to-stdout", "etc/romulus-capture/uuid"],
                        stdin=data, capture_output=True, check=True)
                self.assertIn(result.stdout.decode().strip(),
                              run("mdir", "-i", str(appended_efi), "::"))
            with original.open("rb") as image:
                self.assertEqual(hashlib.file_digest(image, "sha256").hexdigest(), source_hash)
            self.assertTrue(output.with_suffix(".iso.sha256").is_file())


if __name__ == "__main__":
    unittest.main()
