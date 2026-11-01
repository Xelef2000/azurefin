import contextlib
import io
import os
from pathlib import Path
import stat
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import zlib

import bluetooth_address as bt

MAC = bytes.fromhex('123456789ABC')  # Synthetic fixture, never a device address.


def fixture(sector=4096):
    disk = bytearray(1024 * sector)
    entries = bytearray(128 * 128)
    for i, name in enumerate(('DPP', 'DPP_BACKUP')):
        start = 64 + i * 64
        e = memoryview(entries)[i * 128:(i + 1) * 128]
        e[:16] = b'X' * 16
        struct.pack_into('<QQ', e, 32, start, start + 63)
        encoded = name.encode('utf-16-le')
        e[56:56 + len(encoded)] = encoded
        base = start * sector
        disk[base:base + 4] = b'RWFS'
        struct.pack_into('<I', disk, base + 8, 68)
        disk[base + 68:base + 72] = b'RWFS'
        struct.pack_into('<II', disk, base + 76, 136, 244 * 3)
        struct.pack_into('<I', disk, base + 88, 1024)
        # First slot is empty, second is the mixed-case Bluetooth record.
        entry = base + 136 + 244
        for offset, value in ((0, 'BT.Provision'), (98, 'QCOM')):
            encoded = value.encode('utf-16-le')
            disk[entry + offset:entry + offset + len(encoded)] = encoded
        struct.pack_into('<IIII', disk, entry + 196, 256, 8, 1, 0)
        disk[base + 1024:base + 1032] = b'\x01\x06' + MAC
    header = bytearray(sector)
    header[:8] = b'EFI PART'
    struct.pack_into('<II', header, 8, 0x10000, 92)
    first = 2 + (len(entries) + sector - 1) // sector
    struct.pack_into('<QQQQ', header, 24, 1, 1023, first, 1022)
    struct.pack_into('<QIII', header, 72, 2, 128, 128, zlib.crc32(entries))
    struct.pack_into('<I', header, 16, zlib.crc32(header[:92]))
    disk[sector:2 * sector] = header
    disk[2 * sector:2 * sector + len(entries)] = entries
    return disk


class ParserTests(unittest.TestCase):
    def reader(self, data):
        return bt.Reader(lambda size, off: data[off:off + size], len(data))

    def test_both_sector_sizes_and_directory_holes(self):
        for sector in (512, 4096):
            reader = self.reader(fixture(sector))
            self.assertEqual(bt.read_factory(reader), '12:34:56:78:9A:BC')
            self.assertLess(2 * 1024**2 - reader.remaining, 32768)

    def test_header_and_table_checksum_failures(self):
        for offset in (4096 + 56, 8192 + 56):
            disk = fixture()
            disk[offset] ^= 1
            with self.assertRaisesRegex(ValueError, 'checksum'):
                bt.read_factory(self.reader(disk))

    def test_backup_mismatch(self):
        disk = fixture()
        disk[128 * 4096 + 1031] ^= 1
        with self.assertRaisesRegex(ValueError, 'disagree'):
            bt.read_factory(self.reader(disk))

    def test_invalid_record_prefix_length_and_bounds(self):
        for offset, value in ((1024, b'\x02'),
                              (136 + 244 + 200, struct.pack('<I', 9)),
                              (136 + 244 + 208, struct.pack('<I', 0xffffffff)),
                              (68 + 12, struct.pack('<I', 0xffffffff))):
            disk = fixture()
            start = 64 * 4096 + offset
            disk[start:start + len(value)] = value
            with self.assertRaises(ValueError):
                bt.read_factory(self.reader(disk))

    def test_missing_duplicate_and_invalid_address(self):
        for variant in ('missing', 'duplicate', 'zero', 'broadcast'):
            disk = fixture()
            entry = 64 * 4096 + 136 + 244
            if variant == 'missing':
                struct.pack_into('<I', disk, entry + 204, 0)
            elif variant == 'duplicate':
                disk[entry + 244:entry + 488] = disk[entry:entry + 244]
            else:
                disk[64 * 4096 + 1026:64 * 4096 + 1032] = (b'\0' if variant == 'zero' else b'\xff') * 6
            with self.assertRaises((ValueError, bt.argparse.ArgumentTypeError)):
                bt.read_factory(self.reader(disk))

    def test_bounded_and_short_reads(self):
        reader = self.reader(b'1234')
        for offset, size in ((-1, 1), (4, 1), (0, -1)):
            with self.assertRaises(ValueError):
                reader.read(offset, size)
        reader.remaining = 1
        with self.assertRaisesRegex(ValueError, 'budget'):
            reader.read(0, 2)
        with self.assertRaisesRegex(ValueError, 'Short'):
            bt.Reader(lambda n, off: b'', 4096).read(0, 8)


class DeviceTests(unittest.TestCase):
    def test_module_lifetime_and_read_only_flags(self):
        for already_loaded in (False, True):
            for flags in ('0x1000', '0x1400'):
                with self.subTest(loaded=already_loaded, flags=flags), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    compatible, module, mtd = root / 'compatible', root / 'module', root / 'mtd'
                    compatible.write_bytes(b'microsoft,romulus13\0qcom,x1e80100\0')
                    mtd.mkdir()
                    node = mtd / 'mtd0'
                    node.mkdir()
                    # The read-only alias must not be interpreted as a second device.
                    (mtd / 'mtd0ro').mkdir()
                    for name, value in {'name': 'qcom_scm_storage', 'type': 'rom',
                                        'flags': flags, 'dev': '90:0', 'size': '67108864'}.items():
                        (node / name).write_text(value)
                    if already_loaded:
                        module.mkdir()
                    commands = []

                    def run(command, **kwargs):
                        commands.append(command)
                        if '-r' in command:
                            module.rmdir()
                        else:
                            module.mkdir()

                    with patch.object(bt, 'COMPATIBLE', compatible), patch.object(bt, 'MODULE', module), \
                            patch.object(bt, 'MTD', mtd), patch.object(bt.subprocess, 'run', side_effect=run), \
                            patch.object(bt.os, 'open', return_value=99) as opened, \
                            patch.object(bt.os, 'close') as closed, \
                            patch.object(bt.os, 'fstat', return_value=SimpleNamespace(
                                st_mode=stat.S_IFCHR, st_rdev=os.makedev(90, 1))), \
                            patch.object(bt, 'read_factory', return_value='12:34:56:78:9A:BC'):
                        if flags == '0x1000':
                            self.assertEqual(bt.detect(), '12:34:56:78:9A:BC')
                            self.assertEqual(opened.call_args.args[1] & os.O_ACCMODE, os.O_RDONLY)
                            closed.assert_called_once_with(99)
                        else:
                            with self.assertRaisesRegex(ValueError, 'read-only'):
                                bt.detect()
                            opened.assert_not_called()
                        self.assertEqual(module.exists(), already_loaded)
                        self.assertEqual(commands, [] if already_loaded else [
                            ['modprobe', 'qcom_scm_storage', 'probe_readonly=1'],
                            ['modprobe', '-r', 'qcom_scm_storage']])


class ConfigureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name) / 'address'
        self.patch = patch.object(bt, 'CONFIG', self.config)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_explicit_address_bypasses_detection(self):
        with patch.object(bt, 'detect') as detect, patch.object(bt.subprocess, 'run') as run:
            self.assertTrue(bt.configure('12:34:56:78:9a:bc'))
            detect.assert_not_called()
            run.assert_called_once_with(['azurefin-extract-firmware', '--bluetooth-address',
                                         '12:34:56:78:9A:BC'], check=True)

    def test_existing_and_symlink_configuration_preserved(self):
        for symlink in (False, True):
            if symlink:
                self.config.unlink()
                self.config.symlink_to('missing')
            else:
                self.config.touch()
            with patch.object(bt, 'detect') as detect, patch.object(bt.subprocess, 'run') as run:
                self.assertTrue(bt.configure())
                detect.assert_not_called()
                run.assert_not_called()

    def test_auto_success_and_skip(self):
        with patch.object(bt, 'detect', return_value='12:34:56:78:9A:BC') as detect, \
                patch.object(bt.subprocess, 'run') as run:
            self.assertFalse(bt.configure(skip=True))
            detect.assert_not_called()
            run.assert_not_called()
            self.assertTrue(bt.configure())
            detect.assert_called_once()
            run.assert_called_once()

    def test_missing_module_and_corrupt_metadata_are_nonfatal(self):
        for error in (FileNotFoundError(), ValueError(), subprocess.CalledProcessError(1, 'modprobe')):
            with patch.object(bt, 'detect', side_effect=error), \
                    patch.object(bt.subprocess, 'run') as run, contextlib.redirect_stderr(io.StringIO()) as output:
                self.assertFalse(bt.configure())
                self.assertIn('--bluetooth-address', output.getvalue())
                run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
