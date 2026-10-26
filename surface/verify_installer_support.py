"""Check that shipped provisioning code matches the composing checkout."""
from pathlib import Path
import argparse

FILES = ('28-prepare-installer-payload.sh', 'Containerfile.provision',
         'installer_fix_fstab.py')


def verify(source: Path, shipped: Path):
    expected = {Path(name) for name in FILES}
    expected.update(path.relative_to(source) for path in (source / 'build').rglob('*')
                    if path.is_file())
    actual_build = {path.relative_to(shipped) for path in (shipped / 'build').rglob('*')
                    if path.is_file() or path.is_symlink()}
    if actual_build != {path for path in expected if path.parts[0] == 'build'}:
        raise ValueError('Provisioning build file set differs from source checkout')
    for relative in sorted(expected):
        target = shipped / relative
        if target.is_symlink() or not target.is_file():
            raise ValueError(f'Missing or symlinked provisioning file: {relative}')
        if (source / relative).read_bytes() != target.read_bytes():
            raise ValueError(f'Stale provisioning file: {relative}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('shipped', type=Path)
    args = parser.parse_args()
    verify(args.source, args.shipped)
    print('INSTALLER_SUPPORT_MATCHES_SOURCE')
