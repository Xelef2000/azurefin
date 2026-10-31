"""Remove only named intermediates from a marked, newly created ISO workspace."""
from pathlib import Path
import re
import shutil
import sys

MARKER = '.azurefin-iso-workspace'
TOKEN = 'azurefin-iso-workspace-v1\n'
INTERMEDIATES = {
    'installer-oci', 'compose', 'modules', 'surface.iso', 'bundle', 'audit',
    'live-oci', 'live-artifacts', 'seed',
}


def remove(root, names, mountinfo=Path('/proc/self/mountinfo')):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Workspace must be a real directory')
    root = root.resolve(strict=True)
    marker = root / MARKER
    if marker.is_symlink() or marker.read_text() != TOKEN:
        raise ValueError('Unmarked ISO workspace')
    if not names or any(name not in INTERMEDIATES for name in names):
        raise ValueError('Only named ISO intermediates may be removed')
    mounts = [Path(re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)),
                          line.split()[4])) for line in mountinfo.read_text().splitlines()]
    targets = [root / name for name in names]
    # Validate the entire request before deleting anything. Never follow links
    # or recurse through mounted filesystems left by a failed privileged audit.
    for target in targets:
        if target.is_symlink():
            raise ValueError(f'Symlink intermediate: {target}')
        if any(mount == target or target in mount.parents for mount in mounts):
            raise ValueError(f'Mounted intermediate: {target}')
    for target in targets:
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        print(f'Removed build intermediate: {target.name}')


if __name__ == '__main__':
    remove(sys.argv[1], sys.argv[2:])
