#!/usr/bin/python3
"""Remove build identity from the staged live tree after Lorax templates run."""
from pathlib import Path
import stat


def reset_machine_ids(tree):
    root = Path(tree).resolve(strict=True)
    for relative in ('etc/machine-id', 'usr/etc/machine-id', 'var/lib/dbus/machine-id'):
        path = root / relative
        # Preserve standard D-Bus aliases; never follow them onto the builder.
        if path.is_symlink():
            continue
        if not path.exists():
            continue
        if not path.resolve().is_relative_to(root) or not stat.S_ISREG(path.stat().st_mode):
            raise ValueError(f'Unsafe staged machine-id path: {relative}')
        with path.open('wb'):
            pass
        print(f'Reset staged {relative} to zero bytes')
