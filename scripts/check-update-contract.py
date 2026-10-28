#!/usr/bin/env python3
"""Check config from an already signature-verified immutable candidate digest."""
import json
from pathlib import Path
import sys


def check(config, contract):
    labels = config.get('config', {}).get('Labels', {})
    for label, field in (('org.azurefin.firmware-bundle', 'firmware_bundle'),
                         ('org.azurefin.firmware-loader-abi', 'firmware_loader_abi')):
        if not contract.get(field) or labels.get(label) != contract[field]:
            raise ValueError(f'Incompatible or missing {label}; do not promote to this channel')


if __name__ == '__main__':
    try:
        check(json.loads(Path(sys.argv[1]).read_text()), json.loads(Path(sys.argv[2]).read_text()))
    except (ValueError, OSError) as error:
        raise SystemExit(str(error)) from error
