#!/usr/bin/env python3
"""Fail closed on known private firmware or personal configuration in OCI layers.

Fedora's redistributable firmware is allowed. This is a technical release gate,
not a general license review. Scan all layers, including subsequently deleted
files, and known blob hashes even when their names have changed.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile


def forbidden(name):
    name = name.removeprefix('./').lstrip('/')
    parts = PurePosixPath(name).parts
    # Include /usr/etc and OSTree deployment prefixes, not just a flat rootfs.
    etc = name[name.index('etc/'):] if 'etc/' in name else name
    return (name.lower().endswith('.msi') or
            'qcom/x1e80100/microsoft' in name.lower() or
            etc == 'etc/romulus-bluetooth-address' or
            etc.startswith('etc/NetworkManager/system-connections/') or
            etc.startswith('etc/ssh/ssh_host_') or
            '.ssh' in parts or
            etc in ('etc/copr', 'etc/copr.conf') or 'cosign.key' in parts)


def check_file(name, stream, size, hashes):
    if forbidden(name):
        raise ValueError(f'Forbidden release content: {name}')
    if (name.removeprefix('./').lstrip('/') == 'etc/machine-id' or
            name.endswith('/etc/machine-id')) and size:
        raise ValueError('Nonempty machine-id')
    if hashlib.file_digest(stream, 'sha256').hexdigest() in hashes:
        raise ValueError(f'Known Microsoft firmware bytes: {name}')


def audit_tar(path, hashes):
    with tarfile.open(path, 'r|*') as archive:
        for entry in archive:
            if forbidden(entry.name) or ((entry.issym() or entry.islnk()) and forbidden(entry.linkname)):
                raise ValueError(f'Forbidden release path: {entry.name}')
            if entry.isfile():
                with archive.extractfile(entry) as stream:
                    check_file(entry.name, stream, entry.size, hashes)


def audit_oci(root, hashes):
    checked = set()

    def blob(descriptor):
        digest = descriptor['digest']
        algorithm, value = digest.split(':')
        if algorithm != 'sha256' or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Invalid OCI digest')
        path = root / 'blobs/sha256' / value
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != value:
                raise ValueError(f'OCI digest mismatch: {digest}')
        return path

    def manifest(descriptor):
        data = json.loads(blob(descriptor).read_text())
        if 'manifests' in data:
            for child in data['manifests']:
                manifest(child)
            return
        config = json.loads(blob(data['config']).read_text())
        if 'locally-provisioned' in json.dumps(config) or 'do-not-publish' in json.dumps(config):
            raise ValueError('Private image label')
        for layer in data['layers']:
            if layer['digest'] not in checked:
                audit_tar(blob(layer), hashes)
                checked.add(layer['digest'])

    index = json.loads((root / 'index.json').read_text())
    if not index.get('manifests'):
        raise ValueError('Empty OCI index')
    for descriptor in index['manifests']:
        manifest(descriptor)
    print(f'Audited {len(checked)} OCI layers (including deleted content)')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=['oci', 'tree', 'tar'])
    parser.add_argument('path', type=Path)
    parser.add_argument('policy', type=Path)
    args = parser.parse_args()
    policy = json.loads(args.policy.read_text())
    hashes = {item['sha256'] for item in policy['files']}
    if not hashes or any(len(value) != 64 for value in hashes):
        raise ValueError('Invalid firmware denylist')
    # Byte-identical metadata also distributed by Fedora is not private
    # firmware. Microsoft-specific destination paths remain forbidden.
    for shared in policy.get('fedora_shared_metadata', []):
        if (shared['sha256'] not in hashes or
                not shared['source'].endswith('.jsn') or
                not shared.get('rpm') or not shared.get('path')):
            raise ValueError('Invalid Fedora metadata exception')
        hashes.remove(shared['sha256'])
    if args.kind == 'oci':
        audit_oci(args.path, hashes)
    elif args.kind == 'tar':
        audit_tar(args.path, hashes)
    else:
        if not args.path.is_dir() or not any(args.path.iterdir()):
            raise ValueError('Missing or empty audit tree')
        for path in args.path.rglob('*'):
            name = path.relative_to(args.path).as_posix()
            if forbidden(name):
                raise ValueError(f'Forbidden release path: {name}')
            if path.is_file() and not path.is_symlink():
                with path.open('rb') as stream:
                    check_file(name, stream, path.stat().st_size, hashes)
    print('RELEASE_CONTENT_AUDIT_PASSED')


if __name__ == '__main__':
    main()
