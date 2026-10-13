#!/usr/bin/python3
"""Create one USB-capable installer entry with Surface display preloads."""
from pathlib import Path
import re
import sys


def patch(text):
    entries = re.findall(
        r"^menuentry [^\n]+ --id (?:romulus-preload-display|azurefin-install) \{\n([^{}]+)^\}",
        text, re.MULTILINE)
    if len(entries) != 1:
        raise ValueError('Expected exactly one Surface display-preload entry')
    body = entries[0]
    kernels = re.findall(r'^\s*linux(?:efi)?\s+(.+)$', body, re.MULTILINE)
    if len(kernels) != 1:
        raise ValueError('Expected exactly one installer kernel')
    args = kernels[0].split()
    if args[0] != '/images/pxeboot/vmlinuz':
        raise ValueError('Unexpected installer kernel')
    stages = [a for a in args if a.startswith('inst.stage2=')]
    if len(stages) != 1 or not re.fullmatch(r'inst.stage2=hd:LABEL=[A-Za-z0-9_.-]+', stages[0]):
        raise ValueError('Expected a safe ISO label for stage2')
    if sum(a.startswith('inst.ks=') for a in args) != 1:
        raise ValueError('Expected exactly one Kickstart argument')
    if not any(a.startswith('rd.driver.pre=') for a in args):
        raise ValueError('Missing Surface display preloads')
    label = stages[0].split('LABEL=', 1)[1]
    args = [f'inst.ks=hd:LABEL={label}:/azurefin/install.ks'
            if a.startswith('inst.ks=') else a for a in args]
    if any(a.startswith('rd.break') or a in ('inst.rescue', 'rd.live.check') for a in args):
        raise ValueError('Unexpected diagnostic stop in installer entry')
    dtbs = re.findall(r'^\s*devicetree\s+(.+)$', body, re.MULTILINE)
    initrds = re.findall(r'^\s*initrd(?:efi)?\s+(.+)$', body, re.MULTILINE)
    if dtbs != ['/images/dtbs/qcom/x1e80100-microsoft-romulus13.dtb'] or initrds != ['/images/pxeboot/initrd.img']:
        raise ValueError('Unexpected installer DTB or initrd')
    header = re.split(r'^\s*(?:menuentry|submenu)\s', text, maxsplit=1, flags=re.MULTILINE)[0]
    header = re.sub(r'^\s*set (?:default|timeout)=.*\n', '', header, flags=re.MULTILINE)
    return (header.rstrip() + '\n\nset timeout=5\nset default=azurefin-install\n\n'
            "menuentry 'Install Azurefin' --id azurefin-install {\n"
            f"  linux {' '.join(args)}\n"
            f'  devicetree {dtbs[0]}\n'
            f'  initrd {initrds[0]}\n}}\n')


if __name__ == '__main__':
    path = Path(sys.argv[1])
    path.write_text(patch(path.read_text()))
