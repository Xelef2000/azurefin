import pathlib
import subprocess
import tempfile
import tomllib
import unittest


SCRIPT = pathlib.Path(__file__).parent / "build/27-installed-boot.sh"


class InstalledBootTests(unittest.TestCase):
    def test_device_tree_and_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            kernel = root / "usr/lib/modules/7.2.0-azurefin.1.fc44"
            dtb = kernel / "dtb/qcom/x1e80100-microsoft-romulus13.dtb"
            dtb.parent.mkdir(parents=True)
            dtb.write_bytes(bytes.fromhex("d00dfeed") + b"fixture")
            for _ in range(2):
                subprocess.run(["bash", str(SCRIPT), tmp], check=True, capture_output=True)
            self.assertEqual(dtb.read_bytes(), (kernel / "devicetree").read_bytes())
            config = tomllib.loads((root / "usr/lib/bootc/kargs.d/50-romulus.toml").read_text())
            self.assertEqual(config["kargs"], ["clk_ignore_unused", "pd_ignore_unused"])
            self.assertEqual(config["match-architectures"], ["aarch64"])

    def test_refuses_missing_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            kernel = pathlib.Path(tmp) / "usr/lib/modules/7.2.0-azurefin.1.fc44"
            kernel.mkdir(parents=True)
            result = subprocess.run(["bash", str(SCRIPT), tmp], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((kernel / "devicetree").exists())

    def test_refuses_multiple_kernels(self):
        with tempfile.TemporaryDirectory() as tmp:
            for version in ("7.2.0-azurefin.1.fc44", "7.2.0-azurefin.2.fc44"):
                (pathlib.Path(tmp) / "usr/lib/modules" / version).mkdir(parents=True)
            result = subprocess.run(["bash", str(SCRIPT), tmp], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
