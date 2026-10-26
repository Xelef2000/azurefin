#!/usr/bin/python3
"""Report real systemd, PAM/autologin and sudo results to the VM serial log."""
import json
from pathlib import Path
import subprocess
import time


def run(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout.strip()


assert 'azurefin.live=1' in Path('/proc/cmdline').read_text().split()
assert Path('/sys/fs/selinux/enforce').read_text().strip() == '1'
print('AZUREFIN_VM_SELINUX_PASS: enforcing', flush=True)
assert run('findmnt', '-n', '-o', 'FSTYPE', '/') == 'overlay'
assert run('findmnt', '-n', '-o', 'FSTYPE', '-T', '/run/overlayfs') == 'tmpfs'
assert not Path('/var/tmp/azurefin-live-reboot-marker').exists()
Path('/var/tmp/azurefin-live-reboot-marker').touch()
assert run('runuser', '-u', 'liveuser', '--', 'sudo', '-n', 'id', '-u') == '0'
for unit in ('sshd.service', 'sshd.socket'):
    assert run('systemctl', 'show', '-p', 'LoadState', '--value', unit) == 'masked'
print('AZUREFIN_VM_ACCOUNT_PASS: sudo, SSH masks, RAM overlay, fresh-session marker', flush=True)
for attempt in range(120):
    sessions = json.loads(run('loginctl', 'list-sessions', '--json=short'))
    for session in sessions:
        if session.get('user') != 'liveuser':
            continue
        session_id = str(session['session'])
        session_type = run('loginctl', 'show-session', session_id, '-p', 'Type', '--value')
        if session_type not in ('wayland', 'x11'):
            continue
        print(f'AZUREFIN_VM_DESKTOP_PASS: liveuser session={session_id} type={session_type}', flush=True)
        raise SystemExit(0)
    time.sleep(2)
raise SystemExit('AZUREFIN_VM_DESKTOP_FAIL: no graphical liveuser session within 240 seconds')
