#!/usr/bin/python3
"""Read factory Bluetooth provisioning without modifying firmware storage.

RWFS layout follows TravMurav/dtbloader src/qcom.c (BSD-3-Clause), commit
b1bf23e88b779ac323fbcbe547cf3ba939433df3. Only metadata and BT.Provision are
requested; the kernel may read whole flash blocks into its bounce buffer.
"""
import argparse
import fcntl
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import zlib

from postinstall_firmware import address

CONFIG = Path('/etc/romulus-bluetooth-address')
MODULE = Path('/sys/module/qcom_scm_storage')
MTD = Path('/sys/class/mtd')
COMPATIBLE = Path('/sys/firmware/devicetree/base/compatible')
FALLBACK = ('Automatic Bluetooth address detection is unavailable. '
            'Use --bluetooth-address with the factory Bluetooth address from Windows, '
            'or run azurefin-extract-firmware --bluetooth-address MAC. '
            'Existing configuration has not been changed.')


def u32(data, offset):
    return struct.unpack_from('<I', data, offset)[0]


class Reader:
    def __init__(self, pread, size):
        if not 0 < size <= 128 * 1024**2:
            raise ValueError('Unsupported storage size')
        self.pread, self.size, self.remaining = pread, size, 2 * 1024**2

    def read(self, offset, size):
        if not 0 <= offset <= self.size or not 0 <= size <= self.size - offset:
            raise ValueError('Storage read out of bounds')
        if size > self.remaining:
            raise ValueError('Diagnostic read budget exceeded')
        self.remaining -= size
        data = self.pread(size, offset)
        if len(data) != size:
            raise ValueError('Short storage read')
        return data


def dpp_partitions(reader):
    for sector in (512, 4096):
        header = reader.read(sector, sector)
        if header[:8] != b'EFI PART':
            continue
        length = u32(header, 12)
        if not 92 <= length <= sector or u32(header, 8) != 0x10000:
            raise ValueError('Invalid GPT header')
        check = bytearray(header[:length])
        check[16:20] = b'\0' * 4
        if zlib.crc32(check) != u32(header, 16):
            raise ValueError('GPT header checksum mismatch')
        current, backup, first, last = struct.unpack_from('<QQQQ', header, 24)
        if current != 1 or not 2 <= first <= last < backup < reader.size // sector:
            raise ValueError('Invalid GPT geometry')
        table, count, entry_size, checksum = struct.unpack_from('<QIII', header, 72)
        if (not 0 < count <= 4096 or entry_size < 128 or entry_size % 128
                or count * entry_size > 1024**2 or table < 2
                or table * sector + count * entry_size > first * sector):
            raise ValueError('Invalid GPT table bounds')
        entries = reader.read(table * sector, count * entry_size)
        if zlib.crc32(entries) != checksum:
            raise ValueError('GPT table checksum mismatch')
        found = {}
        for i in range(count):
            entry = entries[i * entry_size:(i + 1) * entry_size]
            if entry[:16] == b'\0' * 16:
                continue
            name = entry[56:128].decode('utf-16-le').split('\0')[0]
            if name not in ('DPP', 'DPP_BACKUP'):
                continue
            start, end = struct.unpack_from('<QQ', entry, 32)
            if name in found or not first <= start <= end <= last:
                raise ValueError('Invalid or duplicate DPP partition')
            found[name] = (start * sector, (end - start + 1) * sector)
        if set(found) != {'DPP', 'DPP_BACKUP'}:
            raise ValueError('Both DPP copies are required')
        ranges = sorted(found.values())
        if ranges[0][0] + ranges[0][1] > ranges[1][0]:
            raise ValueError('Overlapping DPP partitions')
        return found
    raise ValueError('No supported GPT found')


def read_record(reader, base, length):
    def read(offset, size):
        if not 0 <= offset <= length or not 0 <= size <= length - offset:
            raise ValueError('RWFS read out of bounds')
        return reader.read(base + offset, size)

    header = read(0, 68)
    if header[:4] != b'RWFS':
        raise ValueError('Missing RWFS header')
    second_offset = u32(header, 8)
    if second_offset < 68:
        raise ValueError('Invalid RWFS second header')
    second = read(second_offset, 68)
    if second[:4] != b'RWFS':
        raise ValueError('Missing RWFS directory header')
    table, size, start = u32(second, 8), u32(second, 12), u32(second, 20)
    if (not 0 < size <= 244 * 4096 or size % 244
            or table < second_offset + 68 or not table + size <= start <= length):
        raise ValueError('Invalid RWFS directory bounds')
    entries = read(table, size)
    matches = []
    for offset in range(0, size, 244):
        entry = entries[offset:offset + 244]
        if not u32(entry, 204):
            continue  # Directory holes are valid, including the first entry.
        name = entry[:98].decode('utf-16-le').split('\0')[0].casefold()
        vendor = entry[98:196].decode('utf-16-le').split('\0')[0].casefold()
        if (vendor, name) != ('qcom', 'bt.provision'):
            continue
        region, size = u32(entry, 196), u32(entry, 200)
        position = start + u32(entry, 208)
        if size != 8 or not size <= region <= length - position:
            raise ValueError('Invalid Bluetooth record bounds')
        payload = read(position, size)
        if payload[:2] != b'\x01\x06':
            raise ValueError('Unsupported Bluetooth provisioning record')
        try:
            matches.append(address(':'.join(f'{b:02X}' for b in payload[2:])))
        except argparse.ArgumentTypeError as error:
            raise ValueError('Invalid factory Bluetooth address') from error
    if len(matches) != 1:
        raise ValueError('Expected exactly one Bluetooth record')
    return matches[0]


def read_factory(reader):
    partitions = dpp_partitions(reader)
    values = [read_record(reader, *partitions[name]) for name in ('DPP', 'DPP_BACKUP')]
    if values[0] != values[1]:
        raise ValueError('DPP Bluetooth copies disagree')
    return values[0]


def detect():
    if b'microsoft,romulus13' not in COMPATIBLE.read_bytes().split(b'\0'):
        raise ValueError('Unsupported device')
    owned = not MODULE.exists()
    try:
        if owned:
            subprocess.run(['modprobe', 'qcom_scm_storage', 'probe_readonly=1'],
                           check=True, capture_output=True, timeout=30)
        nodes = [node for node in MTD.glob('mtd[0-9]*')
                 if re.fullmatch(r'mtd[0-9]+', node.name)
                 and (node / 'name').read_text().strip() == 'qcom_scm_storage']
        if len(nodes) != 1:
            raise ValueError('SCM storage probe did not produce one device')
        node = nodes[0]
        if ((node / 'type').read_text().strip() != 'rom'
                or int((node / 'flags').read_text().strip(), 0) != 0x1000):
            raise ValueError('Refusing storage without read-only ROM flags')
        major, minor = map(int, (node / 'dev').read_text().strip().split(':'))
        fd = os.open('/dev/' + node.name + 'ro', os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            info = os.fstat(fd)
            if not stat.S_ISCHR(info.st_mode) or info.st_rdev != os.makedev(major, minor + 1):
                raise ValueError('Unexpected read-only MTD device node')
            return read_factory(Reader(lambda n, off: os.pread(fd, n, off),
                                       int((node / 'size').read_text())))
        finally:
            os.close(fd)
    finally:
        if owned and MODULE.exists():
            subprocess.run(['modprobe', '-r', 'qcom_scm_storage'], check=True,
                           capture_output=True, timeout=30)


def configure(manual=None, skip=False):
    """Caller holds firmware-store.lock; auto failures never undo firmware setup."""
    if skip:
        return False
    if manual is None and (CONFIG.exists() or CONFIG.is_symlink()):
        print('Keeping existing Bluetooth address configuration; no storage probe needed.')
        return True
    if manual is not None:
        selected = address(manual)
    else:
        try:
            selected = detect()
        except (ValueError, OSError, subprocess.SubprocessError):
            print(FALLBACK, file=sys.stderr)
            return False
    subprocess.run(['azurefin-extract-firmware', '--bluetooth-address', selected], check=True)
    print('Bluetooth address saved for next boot; no Bluetooth service was restarted.')
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group()
    options.add_argument('--bluetooth-address', type=address, help='manual factory address; no probe')
    options.add_argument('--detect-only', action='store_true', help='print factory address without saving')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run with sudo')
    # Share the firmware setup lock, including when used independently.
    from firmware_preflight import trusted_directory
    state = Path('/var/lib/azurefin')
    state.mkdir(mode=0o700, exist_ok=True)
    trusted_directory(state)
    fd = os.open(state / 'firmware-store.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.detect_only:
            print(detect())
        elif not configure(args.bluetooth_address):
            return 1
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(f'Bluetooth setup failed ({type(error).__name__}). '
                         'Manual fallback: azurefin-extract-firmware --bluetooth-address MAC') from None
