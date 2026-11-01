#!/usr/bin/python3
"""Local prerequisites for upstream updates; never stage, delete or reboot."""
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, '/usr/libexec/azurefin')
import firmware_preflight


def validate_status(data, contract):
    state = data.get('status', {})
    if state.get('staged') or state.get('rollbackQueued') or state.get('usrOverlay'):
        raise ValueError('Finish the pending deployment/rollback or remove the development overlay first')
    booted = state.get('booted') or {}
    origin = (booted.get('image') or {}).get('image') or {}
    if booted.get('incompatible') or origin != {
        'image': contract['channel'], 'signature': 'containerPolicy', 'transport': 'registry'
    }:
        raise ValueError('Updates require the supported testing channel with native signature enforcement')


def validate_target(config, contract):
    labels = config.get('config', {}).get('Labels', {})
    if (labels.get('org.azurefin.firmware-bundle') != contract['firmware_bundle']
            or labels.get('org.azurefin.firmware-loader-abi') != contract['firmware_loader_abi']):
        raise ValueError('Channel image lacks the supported firmware contract; refusing update')


def validate_version(state, config):
    """Fail closed on stale channels; explicit rollback is a separate operation."""
    def version(value):
        match = re.fullmatch(r'v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-alpha)?', value or '')
        if not match:
            raise ValueError('Unrecognized OS version; refusing automatic update')
        return (*map(int, match.group(1, 2, 3)), 0 if match.group(4) else 1)

    current = state['status']['booted']['image'].get('version')
    target = config.get('config', {}).get('Labels', {}).get('org.opencontainers.image.version')
    if version(target) < version(current):
        raise ValueError(f'Update channel offers older version {target} than {current}; refusing downgrade')


def main():
    if os.geteuid() != 0:
        raise ValueError('Run with sudo')
    contract = json.loads(Path('/usr/share/azurefin/update-contract.json').read_text())
    if any(arg in ('rd.live.image', 'azurefin.live=1') for arg in Path('/proc/cmdline').read_text().split()):
        raise ValueError('OS updates are not supported in the live session')
    # Keep both streams non-terminal: bootc's privilege/mount setup can mix
    # mount warnings into captured stdout when stderr still points at a TTY.
    state = json.loads(subprocess.check_output(
        ['bootc', 'status', '--json'], text=True, stderr=subprocess.PIPE, timeout=30))
    validate_status(state, contract)
    if firmware_preflight.main() != 0:
        raise ValueError('Repair the firmware store before updating')
    manifest = Path('/usr/share/azurefin/boot-firmware.sha256').read_bytes()
    if hashlib.sha256(manifest).hexdigest() != contract['firmware_bundle']:
        raise ValueError('Booted image does not match this update channel firmware contract')
    # Leave space for another kernel/initramfs without deleting pinned recovery.
    for path, minimum in (('/boot', 768 * 1024**2), ('/var', 10 * 1024**3)):
        usage = os.statvfs(path)
        if usage.f_bavail * usage.f_frsize < minimum:
            raise ValueError(f'Insufficient space on {path}; need {minimum // 1024**2} MiB free. '
                             'Review retained deployments; nothing was deleted.')
    config = json.loads(subprocess.check_output(
        ['skopeo', 'inspect', '--no-creds', '--config', 'docker://' + contract['channel']],
        text=True, timeout=120))
    validate_target(config, contract)
    validate_version(state, config)
    print('Update prerequisites passed. bootc will enforce signatures during the update.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error)) from error
