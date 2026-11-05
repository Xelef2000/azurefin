#!/usr/bin/env python3
"""Retain source notices without extracting archive paths or executing sources.

Discovery is deliberately over-inclusive, not a license determination. Explicit
overrides handle notices in README files/source headers and parent projects.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import zipfile

from inventory_sources import STORE

NOTICE = re.compile(r'(?i)^(licen[cs]e|copying|copyright|notice)([._-]|$)')
LIMIT = 16 * 1024 * 1024


def selected(name, extras):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Unsafe source member name')
    return bool(NOTICE.match(path.name) or 'LICENSES' in path.parts or name in extras)


def entries(source, extras):
    """Yield notice bytes only; never follow archive links."""
    if source.is_dir():
        for path in sorted(source.rglob('*')):
            name = path.relative_to(source).as_posix()
            if selected(name, extras) and path.is_file() and not path.is_symlink():
                if path.stat().st_size > LIMIT:
                    raise ValueError('Oversized notice')
                yield name, path.read_bytes()
    elif zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            for item in archive.infolist():
                if selected(item.filename, extras) and not item.is_dir():
                    if item.file_size > LIMIT:
                        raise ValueError('Oversized notice')
                    yield item.filename, archive.read(item)
    elif source.name.endswith('.tar.lz'):
        names = subprocess.check_output(['bsdtar', '-tf', str(source)], text=True).splitlines()
        for name in names:
            if selected(name, extras) and not name.endswith('/'):
                data = subprocess.check_output(['bsdtar', '-xOf', str(source), '--', name])
                if len(data) > LIMIT:
                    raise ValueError('Oversized notice')
                yield name, data
    elif tarfile.is_tarfile(source):
        with tarfile.open(source, 'r|*') as archive:
            for item in archive:
                if selected(item.name, extras) and item.isfile():
                    if item.size > LIMIT:
                        raise ValueError('Oversized notice')
                    yield item.name, archive.extractfile(item).read()
    elif '.' in extras:
        if source.stat().st_size > LIMIT:
            raise ValueError('Oversized notice')
        yield '.', source.read_bytes()


def retain(source, destination, extras=()):
    records = []
    found = set()
    for name, data in entries(source, extras):
        digest = hashlib.sha256(data).hexdigest()
        target = destination / (digest + '.txt')
        if target.exists() and target.read_bytes() != data:
            raise ValueError('Existing notice differs from its content-addressed name')
        target.write_bytes(data)
        records.append({'path': name, 'sha256': digest, 'bytes': len(data)})
        found.add(name)
    if set(extras) - found:
        raise ValueError(f'Explicit notice paths missing from {source}: {sorted(set(extras) - found)}')
    return {'source': str(source), 'notices': records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-paths', type=Path, required=True)
    parser.add_argument('--overrides', type=Path, required=True)
    parser.add_argument('--vendor', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    roots = ['/' + value for value in args.source_paths.read_text().splitlines()]
    if any(STORE.fullmatch(value) is None for value in roots):
        raise ValueError('Expected store-root source list')
    overrides = json.loads(args.overrides.read_text())
    if set(overrides) - set(roots):
        raise ValueError('Notice overrides must refer to collected sources')
    args.output.mkdir()
    texts = args.output / 'texts'
    texts.mkdir()
    reports = [retain(Path(root), texts, overrides.get(root, [])) for root in sorted(set(roots))]
    vendor_report = retain(args.vendor, texts)
    vendor_report['source'] = 'cargo-vendor'
    reports.append(vendor_report)
    result = {'schema': 1, 'complete_license_inventory': False,
              'scope': 'Source notice discovery plus reviewed explicit paths; source archives retain all headers',
              'sources': reports}
    (args.output / 'index.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    (args.output / 'overrides.json').write_text(json.dumps(overrides, indent=2, sort_keys=True) + '\n')
    print(f'Retained {sum(len(r["notices"]) for r in reports)} notice entries')


if __name__ == '__main__':
    main()
