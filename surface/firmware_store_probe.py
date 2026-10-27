#!/usr/bin/env python3
"""Read-only boot-firmware inventory; not an installer or boot-time loader."""
import argparse
import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import stat

MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024


def inventory(root, policy):
    entries = policy['files']
    if not entries or len(entries) > 256:
        raise ValueError('Invalid file count')
    result, seen, total = [], set(), 0
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for entry in entries:
            target, expected = entry['target'], entry['sha256']
            path = PurePosixPath(target)
            if (path.is_absolute() or '..' in path.parts or not path.parts
                    or str(path) != target or target in seen
                    or not re.fullmatch(r'[a-zA-Z0-9_./-]+', target)
                    or not re.fullmatch(r'[0-9a-f]{64}', expected)):
                raise ValueError('Invalid or duplicate policy entry')
            seen.add(target)
            directory = os.dup(root_fd)
            try:
                for part in path.parts[:-1]:
                    next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY
                                      | os.O_NOFOLLOW, dir_fd=directory)
                    os.close(directory)
                    directory = next_fd
                fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW
                             | os.O_NONBLOCK, dir_fd=directory)
                with os.fdopen(fd, 'rb') as stream:
                    info = os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_FILE:
                        raise ValueError('Not a bounded regular firmware file')
                    digest, count = hashlib.sha256(), 0
                    while chunk := stream.read(1024 * 1024):
                        count += len(chunk)
                        if count > MAX_FILE:
                            raise ValueError('Firmware grew beyond size limit')
                        digest.update(chunk)
                    if count != info.st_size or digest.hexdigest() != expected:
                        raise ValueError(f'Firmware checksum/size mismatch: {target}')
                    total += count
                    if total > MAX_TOTAL:
                        raise ValueError('Firmware set exceeds size limit')
                    result.append({'target': target, 'bytes': count, 'sha256': expected})
            finally:
                os.close(directory)
    finally:
        os.close(root_fd)
    return {'files': result, 'total_bytes': total}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--policy', required=True)
    args = parser.parse_args()
    with open(args.policy) as stream:
        policy = json.load(stream)
    print(json.dumps(inventory(args.root, policy), indent=2))


if __name__ == '__main__':
    main()
