#!/usr/bin/python3
"""Force every installer entry through firmware preparation before partitioning."""
from pathlib import Path
import re
import sys


def patch(text):
    count = 0
    lines = []
    for line in text.splitlines():
        if re.match(r'\s*linux(?:efi)?\s', line):
            line, found = re.subn(r'inst.ks=\S+', 'inst.ks=cdrom:/azurefin/install.ks', line)
            if found != 1:
                raise ValueError('Expected exactly one Kickstart argument per boot entry')
            count += 1
        lines.append(line)
    if not count:
        raise ValueError('Missing boot entries')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    path = Path(sys.argv[1])
    path.write_text(patch(path.read_text()))
