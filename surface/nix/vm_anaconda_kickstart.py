#!/usr/bin/env python3
"""Generate an automated kickstart for the guarded, disposable Anaconda VM only.

Keep the public install source and post-install scripts unchanged. Never ship
the result on public media: it automatically erases the VM's /dev/vda.
"""
import argparse
from pathlib import Path


def generate(public):
    if public.count('\ngraphical\n') != 1:
        raise ValueError('Expected exactly one graphical installer directive')
    automated = '''
text
lang en_US.UTF-8
keyboard us
timezone UTC
eula --agreed
ignoredisk --only-use=vda
clearpart --all --initlabel --drives=vda
autopart --type=plain --fstype=ext4
bootloader --location=mbr
poweroff
'''
    result = public.replace('\ngraphical\n', automated)
    result += '''
%post --erroronfail --interpreter=/bin/bash --log=/var/log/azurefin-nix-install-check.log
set -euxo pipefail
test -s /usr/share/azurefin/nix/installed-image.json
test -x /usr/libexec/azurefin-nix-installer
systemctl is-enabled azurefin-nix-ready.timer
test ! -e /var/lib/nix
test ! -e /var/lib/azurefin/nix/state.json
test ! -e /usr/libexec/azurefin-live-user.py
test ! -e /usr/libexec/azurefin-nix-anaconda-test.sh
if getent passwd liveuser; then exit 1; fi
test -s /var/lib/azurefin/installer/base-oci/index.json
echo AZUREFIN_NIX_ANACONDA_POST_COMPLETE > /dev/ttyAMA0
%end
'''
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('public', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = generate(args.public.read_text())
    # Refuse to replace an existing kickstart, especially the public source.
    with args.output.open('x') as output:
        output.write(result)


if __name__ == '__main__':
    main()
