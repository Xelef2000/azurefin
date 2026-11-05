#!/usr/bin/env python3
"""Collect pinned source trees locally; never download, build, or publish binaries.

Inputs are the verified payload inventory, recursive schema-4 derivations,
`nix flake archive --json`, a reviewed native-source plan, and Cargo vendor tree.
This intentionally produces an intermediate source artifact, not legal clearance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from inventory_sources import STORE, inventory, store_roots
from inventory_vendor import inventory as inventory_vendor
from audit_notice_coverage import coverage, verify_texts


def flake_paths(tree):
    result = {tree['path']}
    for child in tree.get('inputs', {}).values():
        result.update(flake_paths(child))
    if any(STORE.fullmatch(path) is None for path in result):
        raise ValueError('Invalid archived flake source path')
    return result


def native_paths(plan, graph):
    result = set()
    for record in plan:
        data = graph['derivations'][record['derivation']]
        attrs = data.get('structuredAttrs', data.get('env', {}))
        source = attrs.get('src', attrs.get('srcs'))
        patches = attrs.get('patches', [])
        # A stale or manually edited plan must not silently select other sources.
        if source != record['source'] or patches != record['patches']:
            raise ValueError('Native-source plan differs from pinned derivation graph')
        result.update(store_roots([source, patches]))
    return result


def checksum(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('payload', 'derivations', 'flakes', 'native', 'vendor', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--notices', type=Path, help='Optional reviewed notice collection to include')
    args = parser.parse_args()
    args.output = args.output.absolute()
    raw = {name: getattr(args, name).read_bytes()
           for name in ('payload', 'derivations', 'flakes', 'native')}
    reports = {name: json.loads(data) for name, data in raw.items()}
    pins = json.loads(Path(__file__).with_name('artifacts.json').read_text())
    if (reports['payload']['source_revision'] != pins['source_revision'] or
            reports['payload']['installer_sha256'] != pins['artifacts']['aarch64-linux']['sha256']):
        raise ValueError('Payload inventory does not match the pinned ARM64 artifact')
    runtime = inventory(reports['payload'], reports['derivations'])
    roots = (set(runtime['direct_source_roots']) | flake_paths(reports['flakes']) |
             native_paths(reports['native'], reports['derivations']))
    for path in roots:
        if not Path(path).exists() or Path(path).is_symlink():
            raise ValueError(f'Missing or unexpected source root: {path}')
    installer = Path(reports['flakes']['path'])
    vendor = inventory_vendor(installer / 'Cargo.lock', args.vendor)
    notices = None
    if args.notices:
        notices = json.loads((args.notices / 'index.json').read_text())
        if {r['source'] for r in notices['sources']} != roots | {'cargo-vendor'}:
            raise ValueError('Notice collection does not match the collected source roots')
        verify_texts(notices, args.notices / 'texts')
        notice_coverage = coverage(runtime, notices, json.loads(
            Path(__file__).with_name('notice-parents.json').read_text()))
    # No overwrite, including partial previous runs. Retain them for inspection.
    args.output.mkdir()
    evidence = args.output / 'evidence'
    evidence.mkdir()
    sources = args.output / 'sources'
    sources.mkdir()
    for name, data in raw.items():
        (evidence / (name + '.json')).write_bytes(data)
    for name, data in (('runtime', runtime), ('vendor', vendor)):
        (evidence / (name + '.json')).write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    path_list = evidence / 'source-paths.txt'
    path_list.write_text(''.join(path.removeprefix('/') + '\n' for path in sorted(roots)))
    subprocess.run(['tar', '-C', '/', '--sort=name', '--mtime=@0', '--owner=0', '--group=0',
                    '--numeric-owner', '--zstd', '-cf', str(sources / 'source-trees.tar.zst'),
                    '--verbatim-files-from', '-T', str(path_list.resolve())], check=True)
    subprocess.run(['tar', '-C', str(args.vendor.resolve()), '--sort=name', '--mtime=@0',
                    '--owner=0', '--group=0', '--numeric-owner', '--zstd',
                    '-cf', str((sources / 'cargo-vendor.tar.zst').resolve()), '.'], check=True)
    # Preserve the exact collector and its dependencies alongside the evidence.
    recipes = args.output / 'collector'
    recipes.mkdir()
    for name in ('collect_sources.py', 'inventory_sources.py', 'inventory_vendor.py',
                 'inventory_notices.py', 'audit_notice_coverage.py',
                 'notice-overrides.json', 'notice-parents.json', 'SOURCE-REBUILD.md', 'artifacts.json'):
        shutil.copyfile(Path(__file__).with_name(name), recipes / name)
    own_license = Path(__file__).with_name('LICENSE')
    if not own_license.exists():
        own_license = Path(__file__).resolve().parents[2] / 'LICENSE'
    shutil.copyfile(own_license, recipes / 'LICENSE')
    if notices is not None:
        destination = args.output / 'notices'
        destination.mkdir()
        (destination / 'texts').mkdir()
        (destination / 'index.json').write_text(json.dumps(notices, indent=2, sort_keys=True) + '\n')
        for digest in {n['sha256'] for r in notices['sources'] for n in r['notices']}:
            name = digest + '.txt'
            shutil.copyfile(args.notices / 'texts' / name, destination / 'texts' / name)
        (evidence / 'runtime-notice-coverage.json').write_text(
            json.dumps(notice_coverage, indent=2, sort_keys=True) + '\n')
    manifest = {'schema': 1, 'complete_license_inventory': False,
                'installer_sha256': runtime['installer_sha256'],
                'source_revision': runtime['source_revision'],
                'source_root_count': len(roots), 'runtime_output_count': len(runtime['runtime_outputs']),
                'vendor_crate_count': len(vendor['crates']),
                'notice_entries': sum(len(r['notices']) for r in notices['sources']) if notices else 0,
                'scope': 'Local source/notice collection; release review required before publication'}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    files = sorted(path for path in args.output.rglob('*') if path.is_file())
    (args.output / 'SHA256SUMS').write_text(''.join(
        f'{checksum(path)}  {path.relative_to(args.output)}\n' for path in files))
    print(json.dumps(manifest, sort_keys=True))


if __name__ == '__main__':
    main()
