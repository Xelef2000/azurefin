#!/usr/bin/env python3
"""Read the default OSTree BLS entry from a stopped disposable VM disk.

Entry filenames change as deployments are added. Select deployment index zero,
not a fixed filename. This helper never mounts or writes a host block device.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess


def select(entries):
    candidates = []
    for name, text in entries.items():
        fields = {}
        for line in text.splitlines():
            key, sep, value = line.partition(' ')
            if sep:
                if key in fields:
                    raise ValueError(f'Duplicate BLS field: {name}: {key}')
                fields[key] = value
        options = fields.get('options', '').split()
        deployments = [v.removeprefix('ostree=') for v in options if v.startswith('ostree=')]
        if len(deployments) != 1:
            raise ValueError(f'Expected one deployment: {name}')
        if re.fullmatch(r'/ostree/boot\.[01]/default/[0-9a-f]{64}/0', deployments[0]):
            if not fields.get('title', '').endswith('(ostree:0)'):
                raise ValueError('Conflicting default deployment title')
            for field, prefix in (('linux', 'vmlinuz-'), ('initrd', 'initramfs-')):
                if not re.fullmatch(r'/boot/ostree/default-[0-9a-f]{64}/' + prefix + r'[^/\s]+', fields.get(field, '')):
                    raise ValueError(f'Unexpected {field} path')
            candidates.append(text)
    if len(candidates) != 1:
        raise ValueError('Expected exactly one default OSTree deployment')
    return candidates[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('disk', type=Path)
    args = parser.parse_args()
    if not args.disk.is_file() or args.disk.is_symlink():
        raise ValueError('Expected a regular disposable disk image')
    env = dict(os.environ, LIBGUESTFS_BACKEND='direct')
    def read(*command):
        return subprocess.check_output(['guestfish', '--ro', '-a', str(args.disk),
                                        '-m', '/dev/sda2', *command], env=env, text=True)
    entries = {}
    for name in read('ls', '/boot/loader/entries').splitlines():
        if not re.fullmatch(r'ostree-[0-9]+\.conf', name):
            raise ValueError(f'Unexpected BLS entry: {name}')
        entries[name] = read('cat', '/boot/loader/entries/' + name)
    print(select(entries), end='')


if __name__ == '__main__':
    main()
