#!/usr/bin/python3
"""Run only in a disposable Podman container; real account and sudo tests.

The kernel command line and systemd manager are simulated. There is no booted
systemd/GDM in this test, and success is not a graphical-session boot result.
"""
import configparser
import importlib.util
from pathlib import Path
import pwd
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

assert Path('/run/.containerenv').exists(), 'Disposable Podman container required'
accounts_only = '--accounts-only' in sys.argv
emulated = '--emulated' in sys.argv
source = Path('/tests/setup.py')
spec = importlib.util.spec_from_file_location('live_setup', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
real_read = Path.read_text
def real_run(*args):
    result = subprocess.run(args, text=True, capture_output=True)
    if result.returncode:
        print(result.stdout, result.stderr, flush=True)
    result.check_returncode()
    return result


def read(path, *args, **kwargs):
    if path == Path('/proc/cmdline'):
        return 'azurefin.live=1'
    return real_read(path, *args, **kwargs)


def run(*args):
    if accounts_only and args == ('dconf', 'update'):
        return SimpleNamespace(stdout='')
    if args[0] == 'systemctl':
        assert args == ('systemctl', 'mask', '--runtime', '--now', 'sshd.service', 'sshd.socket')
        # No systemd manager in this container: validate masks offline instead.
        return real_run('systemctl', '--root=/', 'mask', 'sshd.service', 'sshd.socket')
    return real_run(*args)


with patch.object(Path, 'read_text', read), patch.object(module, 'run', run):
    module.configure()

account = pwd.getpwnam('liveuser')
assert account.pw_uid >= 1000
assert Path(account.pw_dir).is_dir()
assert Path(account.pw_dir).stat().st_uid == account.pw_uid
shadow = [line for line in Path('/etc/shadow').read_text().splitlines()
          if line.startswith('liveuser:')]
assert len(shadow) == 1 and shadow[0].split(':')[1] == ''
if emulated:
    # Keep policy validation separate from setuid execution under emulation.
    policy = real_run('sudo', '-n', '-l', '-U', 'liveuser').stdout
    assert 'NOPASSWD: ALL' in policy
else:
    assert real_run('runuser', '-u', 'liveuser', '--', 'sudo', '-n', 'id', '-u').stdout.strip() == '0'
for unit in ('sshd.service', 'sshd.socket'):
    assert (Path('/etc/systemd/system') / unit).readlink() == Path('/dev/null')
config = configparser.ConfigParser()
config.read('/etc/gdm/custom.conf')
assert config['daemon'].getboolean('AutomaticLoginEnable')
assert config['daemon']['AutomaticLogin'] == 'liveuser'
assert not config['daemon'].getboolean('InitialSetupEnable')
if not accounts_only:
    assert Path('/etc/dconf/db/azurefin-live').exists()
for schema, key, expected in (() if accounts_only else (
    ('org.gnome.desktop.screensaver', 'lock-enabled', 'false'),
    ('org.gnome.desktop.lockdown', 'disable-lock-screen', 'true'),
)):
    value = real_run('runuser', '-u', 'liveuser', '--',
                     'gsettings', 'get', schema, key).stdout.strip()
    assert value == expected, (schema, key, value)

print('PASS: real liveuser, home ownership, empty password, GDM config and offline SSH masks')
print('SUDO:', 'policy validation only (emulated)' if emulated else 'real sudo -n elevation passed')
print('DCONF:', 'skipped in accounts-only test' if accounts_only else 'live lock-screen settings passed')
print('NOT TESTED: running GDM, PAM login, systemd activation, live boot or reboot persistence')
