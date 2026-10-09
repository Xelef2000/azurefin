"""Reassemble only checksum-verified, previously audited GitHub ISO assets."""
import hashlib
from pathlib import Path
import re
import shutil
import sys


def assemble(tag, source, output):
    if not re.fullmatch(r'v\d+\.\d+\.\d+(?:-alpha)?', tag):
        raise ValueError('Invalid release tag')
    source, output = Path(source), Path(output)
    name = f'azurefin-{tag}-aarch64.iso'
    audit = (source / 'iso-audit.log').read_text()
    if 'FINAL_ISO_CONTENT_AUDIT_PASSED' not in audit.splitlines():
        raise ValueError('Published ISO audit did not pass')
    entries = []
    for line in (source / 'SHA256SUMS').read_text().splitlines():
        match = re.fullmatch(r'([a-f0-9]{64})  (?:\./)?(' + re.escape(name) + r'\.part-\d{3})', line)
        if not match:
            raise ValueError('Unexpected chunk checksum entry')
        entries.append((match[2], match[1]))
    entries.sort()
    if not entries or [entry[0] for entry in entries] != [
            f'{name}.part-{index:03d}' for index in range(len(entries))]:
        raise ValueError('Missing or duplicate ISO chunks')
    expected = (source / 'ISO-SHA256SUM').read_text().strip()
    match = re.fullmatch(r'([a-f0-9]{64})  ' + re.escape(name), expected)
    if not match:
        raise ValueError('Unexpected whole-ISO checksum entry')
    size = sum((source / part).stat().st_size for part, _ in entries)
    if not 0 < size < 10_000_000_000:
        raise ValueError('ISO exceeds conservative SourceForge 10 GB limit or is empty')
    output.mkdir(exist_ok=False)
    total = hashlib.sha256()
    with (output / name).open('xb') as target:
        for part, checksum in entries:
            chunk = hashlib.sha256()
            with (source / part).open('rb') as handle:
                while data := handle.read(8 * 1024 * 1024):
                    chunk.update(data)
                    total.update(data)
                    target.write(data)
            if chunk.hexdigest() != checksum:
                raise ValueError(f'Chunk checksum mismatch: {part}')
    if total.hexdigest() != match[1]:
        raise ValueError('Whole ISO checksum mismatch')
    for metadata in ('ISO-SHA256SUM', 'BUILD-INFO.txt', 'iso-audit.log'):
        shutil.copyfile(source / metadata, output / metadata)
    print(f'Verified complete ISO: {name} ({size} bytes)')


if __name__ == '__main__':
    assemble(*sys.argv[1:])
