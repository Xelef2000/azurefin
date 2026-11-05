#!/usr/bin/env python3
"""Create the backing directory without adopting or chmod-ing existing data."""
import os
from pathlib import Path
import stat


def prepare(parent=Path('/var/lib'), mountpoint=Path('/nix')):
    for path in (parent, mountpoint):
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise RuntimeError(f"Unsafe Nix directory: {path}")
    backing = parent / 'nix'
    try:
        backing.mkdir(mode=0o755)
    except FileExistsError:
        pass
    info = backing.lstat()
    if (not stat.S_ISDIR(info.st_mode)
            or (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) != (0, 0, 0o755)):
        raise RuntimeError("Existing Nix backing directory requires administrator review")


if __name__ == '__main__':
    if os.geteuid() != 0:
        raise SystemExit('Backing directory preparation requires root')
    prepare()
