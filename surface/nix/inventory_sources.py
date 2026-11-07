#!/usr/bin/env python3
"""Match verified payload outputs to a pinned Nix schema-4 derivation graph.

This is a source-collection manifest, not a license-compliance assertion.
No derivations are executed and no paths are downloaded or extracted.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

STORE = re.compile(r'/nix/store/[0-9abcdfghijklmnpqrsvwxyz]{32}-[^ /\n\t"\']+')


def store_roots(value):
    if isinstance(value, str):
        return set(STORE.findall(value))
    if isinstance(value, dict):
        return store_roots(list(value.values()))
    if isinstance(value, (list, tuple)):
        return set().union(*(store_roots(item) for item in value))
    return set()


def inventory(payload, graph):
    if graph.get('version') != 4 or not isinstance(graph.get('derivations'), dict):
        raise ValueError('Only the reviewed Nix derivation JSON schema 4 is supported')
    wanted = set(payload['store_outputs'])
    if not wanted or any(STORE.fullmatch(path) is None for path in wanted):
        raise ValueError('Invalid payload output paths')
    matched = set()
    records = []
    for drv, data in sorted(graph['derivations'].items()):
        attrs = data.get('structuredAttrs', data.get('env', {}))
        for output, details in sorted(data['outputs'].items()):
            path = details.get('path', '')
            path = path if path.startswith('/') else '/nix/store/' + path
            if path not in wanted:
                continue
            matched.add(path)
            source = attrs.get('src', attrs.get('srcs'))
            patches = attrs.get('patches', [])
            # Keep raw attributes too: filtered source trees and generated inputs
            # need the full recipes/parent sources, not just these direct paths.
            records.append({
                'output': path, 'output_name': output, 'derivation': drv,
                'source': source, 'patches': patches,
                'direct_source_roots': sorted(store_roots([source, patches])),
            })
    if matched != wanted:
        raise ValueError(f'Unmatched payload outputs: {sorted(wanted - matched)}')
    return {
        'schema': 1, 'complete_license_inventory': False,
        'scope': 'Direct runtime source/patch inputs; retain full recipes and parent sources separately',
        'installer_sha256': payload['installer_sha256'],
        'source_revision': payload['source_revision'],
        'runtime_outputs': sorted(wanted), 'matches': records,
        'direct_source_roots': sorted({p for r in records for p in r['direct_source_roots']}),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('payload', type=Path)
    parser.add_argument('derivations', type=Path)
    args = parser.parse_args()
    payload, graph = args.payload.read_bytes(), args.derivations.read_bytes()
    result = inventory(json.loads(payload), json.loads(graph))
    result['input_sha256'] = {
        'payload_inventory': hashlib.sha256(payload).hexdigest(),
        'derivation_graph': hashlib.sha256(graph).hexdigest(),
    }
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
