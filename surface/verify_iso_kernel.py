"""Bind an ISO's boot kernel and DTB to the same installed kernel tree."""
import hashlib
from pathlib import Path
import sys

DTB = 'dtb/qcom/x1e80100-microsoft-romulus13.dtb'


def digest(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f'Expected nonempty regular boot file: {path}')
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').digest()


def verify(root, iso, mode):
    if mode not in ('live', 'installer'):
        raise ValueError('Unknown ISO mode')
    trees = sorted((root / 'usr/lib/modules').iterdir())
    if not trees or any(tree.is_symlink() or not tree.is_dir() for tree in trees):
        raise ValueError('Unexpected kernel directory layout')
    if mode == 'live' and len(trees) != 1:
        raise ValueError('Live ISO must contain exactly one kernel tree')
    boot_hash = digest(iso / 'images/pxeboot/vmlinuz')
    matches = [tree for tree in trees if digest(tree / 'vmlinuz') == boot_hash]
    if len(matches) != 1:
        raise ValueError(f'Expected exactly one byte-matching boot kernel, found {len(matches)}')
    tree = matches[0]
    if digest(tree / DTB) != digest(iso / 'images/dtbs/qcom/x1e80100-microsoft-romulus13.dtb'):
        raise ValueError('Boot DTB does not match the selected boot kernel tree')
    print(f'ISO_BOOT_KERNEL_AND_DTB_VERIFIED: {tree.name} (mode={mode}, trees={len(trees)})')
    return tree.name


if __name__ == '__main__':
    verify(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
