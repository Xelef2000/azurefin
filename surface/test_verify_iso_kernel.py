from pathlib import Path
import tempfile
import unittest
from verify_iso_kernel import DTB, verify


class KernelBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'root'
        self.iso = Path(self.temp.name) / 'iso'
        self.put(self.iso / 'images/pxeboot/vmlinuz', b'azurefin-kernel')
        self.put(self.iso / 'images/dtbs/qcom/x1e80100-microsoft-romulus13.dtb', b'azurefin-dtb')
        self.kernel('azurefin', b'azurefin-kernel', b'azurefin-dtb')

    def put(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def kernel(self, name, kernel, dtb):
        tree = self.root / 'usr/lib/modules' / name
        self.put(tree / 'vmlinuz', kernel)
        self.put(tree / DTB, dtb)

    def test_single_live_kernel(self):
        self.assertEqual(verify(self.root, self.iso, 'live'), 'azurefin')

    def test_installer_selects_byte_matching_kernel_not_first_dtb(self):
        self.kernel('aaa-stock', b'stock-kernel', b'stock-dtb')
        self.assertEqual(verify(self.root, self.iso, 'installer'), 'azurefin')

    def test_multiple_live_kernels_rejected(self):
        self.kernel('stock', b'stock-kernel', b'stock-dtb')
        with self.assertRaisesRegex(ValueError, 'exactly one kernel tree'):
            verify(self.root, self.iso, 'live')

    def test_mixed_kernel_and_dtb_rejected(self):
        self.kernel('stock', b'stock-kernel', b'stock-dtb')
        self.put(self.iso / 'images/pxeboot/vmlinuz', b'stock-kernel')
        with self.assertRaisesRegex(ValueError, 'DTB does not match'):
            verify(self.root, self.iso, 'installer')

    def test_unknown_kernel_rejected(self):
        self.put(self.iso / 'images/pxeboot/vmlinuz', b'unknown')
        with self.assertRaisesRegex(ValueError, 'found 0'):
            verify(self.root, self.iso, 'installer')

    def test_ambiguous_kernel_rejected(self):
        self.kernel('duplicate', b'azurefin-kernel', b'azurefin-dtb')
        with self.assertRaisesRegex(ValueError, 'found 2'):
            verify(self.root, self.iso, 'installer')

    def test_symlink_kernel_rejected(self):
        path = self.root / 'usr/lib/modules/azurefin/vmlinuz'
        path.unlink()
        path.symlink_to(self.iso / 'images/pxeboot/vmlinuz')
        with self.assertRaisesRegex(ValueError, 'regular boot file'):
            verify(self.root, self.iso, 'installer')


if __name__ == '__main__':
    unittest.main()
