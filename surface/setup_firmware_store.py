#!/usr/bin/python3
"""Provision verified firmware independently of the immutable OS image."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, '/usr/libexec/azurefin')
from firmware_bundle import manifest, provision
from firmware_preflight import check_bundle, check_space, trusted_directory, validate_mount
from postinstall_firmware import address
from bluetooth_address import configure as configure_bluetooth

POLICY = Path('/usr/share/azurefin/firmware-policy.json')
MANIFEST = Path('/usr/share/azurefin/boot-firmware.sha256')
BOOT = Path('/boot')
STATE = Path('/var/lib/azurefin')
MIN_EXTRACTION_FREE = 30 * 1024**3


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def validate_host(mounts, cmdline, status):
    host = status.get('status', {})
    if (not host.get('booted') or host.get('staged') or host.get('rollbackQueued')
            or host.get('usrOverlay')):
        raise ValueError('Boot a normal deployment with no staged update or queued rollback first')
    if any(arg in ('azurefin.live=1', 'rd.live.image') for arg in cmdline.split()):
        raise ValueError('Firmware setup requires an installed system, not the live session')
    entries = mounts.get('filesystems', [])
    uuid = entries[0].get('uuid', '') if len(entries) == 1 else ''
    # Apply the existing strict mount checks before adding the local argument.
    uuid = validate_mount(mounts, f'azurefin.boot_uuid={uuid}')
    arguments = [arg for arg in cmdline.split() if arg.startswith('azurefin.boot_uuid=')]
    if arguments not in ([], [f'azurefin.boot_uuid={uuid}']):
        raise ValueError('Conflicting or duplicate firmware boot UUID; refusing to replace it')
    return uuid


def seed_extractor(root):
    """The existing extractor expects a writable Fedora board-data tree."""
    relative = Path('usr/lib/firmware/ath12k/WCN7850/hw2.0')
    destination = root / relative
    destination.mkdir(parents=True)
    for suffix in ('', '.xz', '.zst'):
        source = Path('/') / relative / ('board-2.bin' + suffix)
        if source.is_file():
            shutil.copyfile(source, destination / source.name)
            return
    raise ValueError('Fedora WCN7850 board data is missing')


def check_extraction_space(path):
    if shutil.disk_usage(path).free < MIN_EXTRACTION_FREE:
        raise ValueError('Firmware extraction requires at least 30 GiB free on /var/lib/azurefin')


def install_store(source, policy, expected, uuid):
    for directory in (BOOT, BOOT / 'azurefin', BOOT / 'azurefin/firmware'):
        if directory != BOOT:
            directory.mkdir(mode=0o700, exist_ok=True)
        trusted_directory(directory)
    destination = provision(source, BOOT / 'azurefin/firmware', policy)
    check_bundle(BOOT, policy, expected)
    # Last operation: a failed copy must never opt the machine into the loader.
    # Keep all other arguments, including LUKS. Do not stage or switch images.
    run('ostree', 'admin', 'instutil', 'set-kargs', '--merge',
        f'--replace=azurefin.boot_uuid={uuid}')
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--download', action='store_true')
    source.add_argument('--msi', type=Path)
    source.add_argument('--from-installed', action='store_true',
                        help='reuse and verify firmware from the currently booted private image')
    bluetooth = parser.add_mutually_exclusive_group()
    bluetooth.add_argument('--bluetooth-address', type=address,
                           help='manual factory address; bypass automatic detection')
    bluetooth.add_argument('--skip-bluetooth', action='store_true',
                           help='skip optional Bluetooth address detection/configuration')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run with sudo')
    os.umask(0o077)
    STATE.mkdir(mode=0o700, exist_ok=True)
    trusted_directory(STATE)
    fd = os.open(STATE / 'firmware-store.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        mounts = json.loads(run('findmnt', '--json', '--mountpoint', '/boot', '--output',
                               'TARGET,FSTYPE,UUID,OPTIONS', capture_output=True).stdout)
        status = json.loads(run('bootc', 'status', '--json', capture_output=True).stdout)
        uuid = validate_host(mounts, Path('/proc/cmdline').read_text(), status)
        trusted_directory(BOOT)
        policy = json.loads(POLICY.read_text())
        expected = MANIFEST.read_bytes()
        if manifest(policy) != expected:
            raise ValueError('Image policy and boot manifest differ')
        usage = os.statvfs(BOOT)
        # Leave the diagnostic headroom even after the largest permitted bundle.
        check_space(usage.f_bavail * usage.f_frsize - 128 * 1024 * 1024)
        if args.from_installed:
            destination = install_store(Path('/usr/lib/firmware'), policy, expected, uuid)
        else:
            check_extraction_space(STATE)
            workspace = Path(tempfile.mkdtemp(prefix='firmware-extraction.', dir=STATE))
            print(f'Extraction workspace (retained for diagnosis): {workspace}', flush=True)
            root = workspace / 'root'
            seed_extractor(root)
            msi = '--download' if args.download else str(args.msi.resolve(strict=True))
            run('azurefin-extract-firmware', '--config', str(POLICY), msi, str(root),
                env={**os.environ, 'TMPDIR': str(workspace)})
            destination = install_store(root / 'usr/lib/firmware', policy, expected, uuid)
        configure_bluetooth(args.bluetooth_address, skip=args.skip_bluetooth)
        print(f'Verified persistent firmware store: {destination}')
        print('Reboot when ready to test the loader. No OS image was changed; automatic updates remain unchanged.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error)) from error
