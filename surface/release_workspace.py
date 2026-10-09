#!/usr/bin/python3
"""Select an existing USB workspace; execute tools only from read-only ISO media."""
import json
import os
from pathlib import Path
import re
import subprocess


def candidates(devices):
    result = []
    for disk in devices:
        if disk.get('type') != 'disk' or disk.get('tran') != 'usb':
            continue
        if not re.fullmatch(r'/dev/sd[a-z]+', disk['name']):
            continue
        for part in disk.get('children', []):
            if (part.get('type') == 'part' and part.get('label') == 'AZUREFIN_WORK'
                    and part.get('fstype') in ('ext4', 'xfs', 'btrfs')
                    and re.fullmatch(r'/dev/sd[a-z]+[0-9]+', part['name'])
                    and not any(part.get('mountpoints') or [])):
                result.append((part['name'], Path(disk['name']).name))
    return result


def main():
    source = Path('/run/install/repo/azurefin')
    from installer_prepare import open_console
    reader, writer = open_console('/dev/tty8')
    subprocess.run(['chvt', '8'], check=True)
    with reader, writer:
        while True:
            writer.write('Connect a USB workspace labeled AZUREFIN_WORK (ext4/XFS/Btrfs, '
                         'at least 30 GiB free). No disk will be formatted.\n'
                         'Press Enter to scan, or q to cancel: ')
            answer = reader.readline()
            if not answer or answer.strip().lower() == 'q':
                raise SystemExit('Workspace selection cancelled')
            devices = json.loads(subprocess.check_output([
                'lsblk', '--json', '--paths', '-o',
                'NAME,TYPE,TRAN,FSTYPE,LABEL,MOUNTPOINTS'], text=True))['blockdevices']
            matches = candidates(devices)
            if len(matches) != 1:
                writer.write('Exactly one unmounted workspace is required; found '
                             f'{len(matches)}. Disconnect duplicate workspace drives.\n')
                continue
            device, disk = matches[0]
            writer.write(f'Use {device} for temporary firmware preparation? [yes/no]: ')
            if reader.readline().strip().lower() != 'yes':
                continue
            break
    target = Path('/run/azurefin-work')
    target.mkdir(exist_ok=True)
    subprocess.run(['mount', '-o', 'rw,nosuid,nodev', device, str(target)], check=True)
    # Refuse workspace-controlled links at paths the preparation code will write.
    for name in ('launcher.log', 'runs'):
        if (target / name).is_symlink():
            raise SystemExit(f'Unsafe workspace symlink: {name}')
    os.environ['AZUREFIN_INSTALLER_SOURCE'] = str(source)
    os.execv('/usr/bin/python3', ['python3', str(source / 'support/installer_prepare.py'), disk])


if __name__ == '__main__':
    main()
