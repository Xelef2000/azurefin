#!/usr/bin/env python3
"""Require source-notice coverage for every runtime output, retaining parent notices.

This checks collected evidence, not the legal sufficiency of license selections.
"""
import argparse
import hashlib
import json
from pathlib import Path


def coverage(runtime, notices, parents):
    wanted = set(runtime['runtime_outputs'])
    if set(parents) - wanted:
        raise ValueError('Stale parent-source mappings')
    index = {record['source']: record['notices'] for record in notices['sources']}
    result = []
    for output in sorted(wanted):
        sources = {record['source'] for record in runtime['matches']
                   if record['output'] == output and isinstance(record['source'], str)}
        if output in parents:
            parent = parents[output]
            if not index.get(parent):
                raise ValueError(f'Missing parent notices for {output}')
            sources.add(parent)
        evidence = [{'source': source, 'notices': index[source]}
                    for source in sorted(sources) if index.get(source)]
        if not evidence:
            raise ValueError(f'No collected source notices for {output}')
        result.append({'output': output, 'evidence': evidence})
    return {'schema': 1, 'complete_license_inventory': False,
            'scope': 'Runtime source-notice coverage; static installer and license interpretation reviewed separately',
            'runtime_outputs': result}


def verify_texts(notices, texts):
    for record in notices['sources']:
        for notice in record['notices']:
            digest = notice['sha256']
            if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                raise ValueError('Malformed notice digest')
            path = texts / (digest + '.txt')
            if path.is_symlink():
                raise ValueError('Notice text must not be a symlink')
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != digest or len(data) != notice['bytes']:
                raise ValueError('Missing or modified notice text')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runtime', type=Path)
    parser.add_argument('notices', type=Path)
    parser.add_argument('parents', type=Path)
    parser.add_argument('--texts', type=Path, required=True)
    args = parser.parse_args()
    notices = json.loads(args.notices.read_text())
    verify_texts(notices, args.texts)
    result = coverage(json.loads(args.runtime.read_text()), notices,
                      json.loads(args.parents.read_text()))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
