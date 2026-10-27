#!/usr/bin/env python3
"""Versioned local firmware bundles and the public initramfs hash manifest.

The destination is a trusted, root-owned directory on the mounted boot
filesystem. Callers must validate the mount and its parent directories first.
No old bundle is removed and no existing bundle is overwritten.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile

from firmware_store_probe import inventory, MAX_FILE, MAX_TOTAL


def manifest(policy):
    entries = policy.get('files')
    if not isinstance(entries, list) or not 1 <= len(entries) <= 256:
        raise ValueError('Invalid firmware file list')
    rows, seen = [], set()
    for entry in entries:
        target, digest = entry.get('target'), entry.get('sha256')
        if not isinstance(target, str) or not isinstance(digest, str):
            raise ValueError('Invalid policy fields')
        path = PurePosixPath(target)
        if (not re.fullmatch(r'[a-zA-Z0-9_./-]+', target)
                or path.is_absolute() or '..' in path.parts or not path.parts
                or str(path) != target or target in seen
                or not re.fullmatch(r'[0-9a-f]{64}', digest)):
            raise ValueError('Unsafe or duplicate policy entry')
        seen.add(target)
        rows.append(f'{digest}  {target}\n')
    return ''.join(sorted(rows)).encode('ascii')


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def copy_verified(source, destination, policy):
    """Hash the same opened bytes that are copied, without source symlinks."""
    root = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    total = 0
    try:
        for entry in policy['files']:
            path = PurePosixPath(entry['target'])
            directory = os.dup(root)
            try:
                for component in path.parts[:-1]:
                    child = os.open(component, os.O_RDONLY | os.O_DIRECTORY
                                    | os.O_NOFOLLOW, dir_fd=directory)
                    os.close(directory)
                    directory = child
                fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=directory)
                with os.fdopen(fd, 'rb') as stream:
                    info = os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_FILE:
                        raise ValueError('Invalid firmware file type/size')
                    target = destination / entry['target']
                    target.parent.mkdir(parents=True, exist_ok=True)
                    digest, size = hashlib.sha256(), 0
                    with target.open('xb') as output:
                        while chunk := stream.read(1024 * 1024):
                            size += len(chunk)
                            total += len(chunk)
                            if size > MAX_FILE or total > MAX_TOTAL:
                                raise ValueError('Firmware size limit exceeded')
                            digest.update(chunk)
                            output.write(chunk)
                        if size != info.st_size or digest.hexdigest() != entry['sha256']:
                            raise ValueError('Firmware checksum/size mismatch')
                        output.flush()
                        os.fsync(output.fileno())
            finally:
                os.close(directory)
    finally:
        os.close(root)


def provision(source, store, policy):
    contents = manifest(policy)
    bundle_id = hashlib.sha256(contents).hexdigest()
    store = Path(store)
    if store.is_symlink() or not store.is_dir():
        raise ValueError('Bundle store must be an existing non-symlink directory')
    destination = store / bundle_id
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_dir():
            raise ValueError('Invalid existing bundle')
        inventory(destination, policy)
        return destination
    temporary = Path(tempfile.mkdtemp(prefix='.preparing-', dir=store))
    try:
        copy_verified(source, temporary, policy)
        inventory(temporary, policy)
        for directory, _, _ in os.walk(temporary, topdown=False):
            sync_directory(directory)
        # Existing valid bundles are nonempty, so rename cannot replace one.
        # Callers serialize provisioning; the store is not writable by users.
        os.rename(temporary, destination)
        sync_directory(store)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', required=True, type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--store', type=Path)
    parser.add_argument('--emit-manifest', action='store_true')
    args = parser.parse_args()
    policy = json.loads(args.policy.read_text())
    if args.emit_manifest:
        print(manifest(policy).decode('ascii'), end='')
        return
    if args.source is None or args.store is None:
        parser.error('--source and --store are required for provisioning')
    print(provision(args.source, args.store, policy))


if __name__ == '__main__':
    main()
