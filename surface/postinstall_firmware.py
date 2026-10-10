#!/usr/bin/python3
"""Provision a private bootc deployment after account setup, never in Anaconda."""
import argparse
import fcntl
import os
from pathlib import Path
import re
import subprocess


SEED = Path('/var/lib/azurefin/installer')
RUNS = Path('/var/lib/azurefin/provisioning')


def address(value):
    value = value.upper()
    if (not re.fullmatch(r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}', value)
            or value in ('00:00:00:00:00:00', 'FF:FF:FF:FF:FF:FF')):
        raise argparse.ArgumentTypeError('Use the Bluetooth public address from Windows, not the Wi-Fi MAC.')
    return value


def ready_payload(value, runs):
    path = Path(value)
    if (path.name != 'container' or path.parent.parent != runs
            or not re.fullmatch(r'azurefin-provision\.[A-Za-z0-9]+', path.parent.name)
            or path.is_symlink() or path.parent.is_symlink()):
        raise RuntimeError('Preparation returned an unexpected payload path')
    if (path.parent / 'READY').read_text().strip() != str(path):
        raise RuntimeError('Missing or mismatched preparation success marker')
    for name in ('index.json', 'oci-layout'):
        if not (path / name).is_file():
            raise RuntimeError('Incomplete OCI payload')
    return path


def prepare(seed, runs, msi):
    expected = (seed / 'base-image-id').read_text().strip()
    if not re.fullmatch(r'[a-f0-9]{64}', expected):
        raise RuntimeError('Invalid pinned bootstrap image ID')
    command = ['bash', str(seed / 'support/28-prepare-installer-payload.sh'),
               str(seed / 'base-oci'), expected, str(runs)]
    if msi is not None:
        command.append(str(msi))
    payload = None
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True) as process:
        for line in process.stdout:
            print(line, end='', flush=True)
            if line.startswith('PAYLOAD_READY: '):
                payload = ready_payload(line.removeprefix('PAYLOAD_READY: ').strip(), runs)
        if process.wait() != 0 or payload is None:
            raise RuntimeError('Firmware preparation failed; the booted deployment was not replaced')
    return payload


def main():
    parser = argparse.ArgumentParser(description=(
        'Install verified Surface firmware in a private local OS image. '
        'Needs 30 GiB free on the internal filesystem. No automatic reboot. '
        'Use USB Ethernet for downloads; built-in Wi-Fi needs this firmware.'))
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--download', action='store_true', help='download the checksum-pinned Microsoft MSI')
    source.add_argument('--msi', type=Path, help='use a supported local MSI (no network required)')
    parser.add_argument('--bluetooth-address', type=address, help='optional factory Bluetooth public address')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run with sudo')
    msi = args.msi.resolve(strict=True) if args.msi else None
    if msi is not None and not msi.is_file():
        parser.error('MSI must be a regular file')
    if not SEED.is_dir() or SEED.is_symlink():
        parser.error('Installer seed is missing; use the post-install provisioning installer')
    os.umask(0o077)
    RUNS.mkdir(parents=True, exist_ok=True)
    if RUNS.is_symlink():
        parser.error('Refusing a symlink workspace')
    # Only one local deployment preparation may run at a time.
    with (RUNS / 'setup.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        subprocess.run(['bootc', 'status'], check=True)
        print('Preparing firmware on the installed disk. No partition changes or automatic reboot.', flush=True)
        payload = prepare(SEED, RUNS, msi)
        # Keep the OCI source on persistent storage for this deployment.
        subprocess.run(['bootc', 'switch', '--transport', 'oci', str(payload)], check=True)
        if args.bluetooth_address:
            subprocess.run(['azurefin-extract-firmware', '--bluetooth-address',
                            args.bluetooth_address], check=True)
        print('Firmware-enabled OS staged. Reboot when ready; keep the workspace until boot is verified.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error)) from error
