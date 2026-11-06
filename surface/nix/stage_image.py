#!/usr/bin/env python3
"""Stage verified offline resources into an image; never initialize a store."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile

from audit_notice_coverage import verify_texts
from verify_artifact import verify

RESOURCES = Path(__file__).resolve().parent
RUNTIME_FILES = ('adapt_plan.py', 'directory.py', 'initialize.py', 'lifecycle.py',
                 'verify_artifact.py', 'artifacts.json', 'nix.conf', 'USER-GUIDE.md')
UNITS = ('azurefin-nix-directory.service', 'azurefin-nix-initialize.service',
         'azurefin-nix-ready.service', 'azurefin-nix-ready.timer', 'nix-daemon.service', 'nix.mount')


def verify_asset(path, pin):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if path.stat().st_size != pin['bytes'] or digest != pin['sha256']:
        raise ValueError('Source/notice asset does not match pin')


def notice_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Unsafe notice path')
    name = str(path)
    if name not in ('notices/index.json', 'evidence/runtime-notice-coverage.json',
                    'collector/notice-parents.json') and not re.fullmatch(r'notices/texts/[0-9a-f]{64}\.txt', name):
        raise ValueError(f'Unexpected notice member: {name}')
    return name


def unpack_notices(archive, destination):
    seen = set()
    with subprocess.Popen(['zstd', '-dc', str(archive)], stdout=subprocess.PIPE) as process:
        with tarfile.open(fileobj=process.stdout, mode='r|') as stream:
            for member in stream:
                if member.isdir() and member.name.rstrip('/') in ('notices', 'notices/texts'):
                    continue
                name = notice_path(member.name)
                if not member.isfile() or name in seen or member.size > 32 * 1024 * 1024:
                    raise ValueError('Unsafe or duplicate notice member')
                seen.add(name)
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with stream.extractfile(member) as source, target.open('xb') as output:
                    shutil.copyfileobj(source, output)
        if process.wait() != 0:
            raise ValueError('Notice decompression failed')
    index = json.loads((destination / 'notices/index.json').read_text())
    verify_texts(index, destination / 'notices/texts')


def stage(root, installer, notices):
    manifest = json.loads((RESOURCES / 'artifacts.json').read_text())
    release = manifest['source_release']
    if release['architecture'] != 'aarch64-linux' or release['installer_sha256'] != manifest['artifacts']['aarch64-linux']['sha256']:
        raise ValueError('Source release does not match installer')
    verify(installer, manifest['artifacts']['aarch64-linux'])
    verify_asset(notices, release['notices'])
    mountpoint = root / 'nix'
    if mountpoint.is_symlink() or (mountpoint.exists() and
            (not mountpoint.is_dir() or any(mountpoint.iterdir()))):
        raise ValueError('Image /nix must be an empty real directory')
    # Validate the complete notice archive before changing the image tree.
    with tempfile.TemporaryDirectory(prefix='azurefin-nix-notices-') as temporary:
        extracted = Path(temporary)
        unpack_notices(notices, extracted)
        destination = root / 'usr/share/azurefin/nix'
        if destination.exists():
            raise ValueError('Nix integration is already staged')
        destination.mkdir(parents=True)
        for name in RUNTIME_FILES:
            shutil.copyfile(RESOURCES / name, destination / name)
        shutil.copytree(extracted, root / 'usr/share/licenses/azurefin-nix')
        own_license = RESOURCES / 'LICENSE'
        if not own_license.exists():
            own_license = RESOURCES.parents[1] / 'LICENSE'
        shutil.copyfile(own_license,
                        root / 'usr/share/licenses/azurefin-nix/Azurefin-LICENSE')
    def install(source, relative, mode=0o644):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(mode)
    install(installer, 'usr/libexec/azurefin-nix-installer', 0o755)
    install(RESOURCES / 'azurefin-nix.sh', 'etc/profile.d/azurefin-nix.sh')
    for name in UNITS:
        install(RESOURCES / 'systemd' / name, 'usr/lib/systemd/system/' + name)
    (destination / 'installed-image.json').write_text('{"schema": 1}\n')
    mountpoint.mkdir(mode=0o755, exist_ok=True)
    wants = root / 'etc/systemd/system/timers.target.wants'
    wants.mkdir(parents=True, exist_ok=True)
    (wants / 'azurefin-nix-ready.timer').symlink_to('/usr/lib/systemd/system/azurefin-nix-ready.timer')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--installer', type=Path, required=True)
    parser.add_argument('--notices', type=Path, required=True)
    args = parser.parse_args()
    stage(args.root, args.installer, args.notices)


if __name__ == '__main__':
    main()
