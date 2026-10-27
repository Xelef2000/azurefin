#!/usr/bin/env python3
"""Read-only firmware-store diagnostic; does not authorize or stage an update.

Run against the booted image's policy. A future updater must separately verify
the target image, check its policy, serialize provisioning and staging, and
preserve rollback bundles. This check is only a point-in-time snapshot.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

from firmware_bundle import manifest
from firmware_store_probe import inventory

MIN_FREE = 512 * 1024 * 1024  # Conservative diagnostic floor, not a size guarantee.
UUID = re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')


def validate_mount(data, cmdline):
    mounts = data.get('filesystems', [])
    if len(mounts) != 1:
        raise ValueError('Expected one separate /boot filesystem')
    mount = mounts[0]
    if mount.get('target') != '/boot' or mount.get('fstype') != 'ext4':
        raise ValueError('/boot must be a separate ext4 mount')
    uuid = mount.get('uuid')
    if not isinstance(uuid, str) or not UUID.fullmatch(uuid):
        raise ValueError('Missing or invalid boot filesystem UUID')
    options = set(mount.get('options', '').split(','))
    if 'rw' not in options or 'ro' in options:
        raise ValueError('/boot is not mounted read-write')
    arguments = [item.split('=', 1)[1] for item in cmdline.split()
                 if item.startswith('azurefin.boot_uuid=')]
    if arguments != [uuid]:
        raise ValueError('Expected exactly one azurefin.boot_uuid matching /boot')
    return uuid


def trusted_directory(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError(f'Expected root-owned, non-symlink directory without group/other write: {path}')


def check_bundle(boot, policy, expected_manifest):
    contents = manifest(policy)
    if contents != expected_manifest:
        raise ValueError('Image manifest does not match image firmware policy')
    bundle_id = hashlib.sha256(contents).hexdigest()
    store = boot / 'azurefin' / 'firmware'
    for path in (boot, boot / 'azurefin', store, store / bundle_id):
        trusted_directory(path)
    result = inventory(store / bundle_id, policy)
    return {'bundle_id': bundle_id, 'files': len(result['files']),
            'firmware_bytes': result['total_bytes']}


def check_space(available):
    if available < MIN_FREE:
        raise ValueError(f'Insufficient /boot headroom: {available} bytes free; '
                         f'diagnostic minimum is {MIN_FREE}. Review retained deployments; do not delete blindly.')


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo; this diagnostic only reads system state.')
    result = {'read_only': True, 'errors': []}
    try:
        mounts = json.loads(subprocess.check_output(
            ['findmnt', '--json', '--mountpoint', '/boot', '--output', 'TARGET,FSTYPE,UUID,OPTIONS'],
            text=True, timeout=15))
        result['boot_uuid'] = validate_mount(mounts, Path('/proc/cmdline').read_text())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        result['errors'].append(str(error))
    # Do not traverse an unexpected mount after mount/UUID validation failed.
    if not result['errors']:
        try:
            policy = json.loads(Path('/usr/share/azurefin/firmware-policy.json').read_text())
            expected = Path('/usr/share/azurefin/boot-firmware.sha256').read_bytes()
            result.update(check_bundle(Path('/boot'), policy, expected))
        except (OSError, ValueError) as error:
            result['errors'].append(str(error))
        try:
            usage = os.statvfs('/boot')
            result['boot_available_bytes'] = usage.f_bavail * usage.f_frsize
            check_space(result['boot_available_bytes'])
        except (OSError, ValueError) as error:
            result['errors'].append(str(error))
    result['diagnostic_passed'] = not result['errors']
    result['note'] = 'Not a signature check, target-image preflight, or authorization to enable automatic updates.'
    print(json.dumps(result, indent=2))
    return 0 if result['diagnostic_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
