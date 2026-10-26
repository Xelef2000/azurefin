#!/usr/bin/python3
"""Create the temporary desktop account before GDM, only on live media."""
import configparser
from pathlib import Path
import subprocess


def run(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True)


def configure(root=Path('/')):
    # Both checks are deliberate: a kernel argument alone must not turn an
    # installed system into a passwordless desktop.
    if 'azurefin.live=1' not in (root / 'proc/cmdline').read_text().split():
        raise RuntimeError('Not an Azurefin live boot')
    fs = run('findmnt', '-n', '-o', 'FSTYPE', '/').stdout.strip()
    if fs not in ('overlay', 'tmpfs'):
        raise RuntimeError(f'Refusing non-ephemeral root filesystem: {fs}')
    passwd = (root / 'etc/passwd').read_text()
    if any(line.split(':')[0] == 'liveuser' for line in passwd.splitlines()):
        raise RuntimeError('Refusing to change an existing liveuser account')

    # Stop remote entry points before unlocking any account. Failure is fatal.
    run('systemctl', 'mask', '--runtime', '--now', 'sshd.service', 'sshd.socket')
    run('useradd', '--create-home', '--groups', 'wheel', '--shell', '/bin/bash', 'liveuser')
    run('passwd', '--delete', 'liveuser')
    sudoers = root / 'etc/sudoers.d/90-azurefin-live'
    sudoers.parent.mkdir(parents=True, exist_ok=True)
    sudoers.write_text('liveuser ALL=(ALL) NOPASSWD: ALL\n')
    sudoers.chmod(0o440)
    run('visudo', '-cf', str(sudoers))

    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    path = root / 'etc/gdm/custom.conf'
    config.read(path)
    if not config.has_section('daemon'):
        config.add_section('daemon')
    config['daemon'].update(AutomaticLoginEnable='True', AutomaticLogin='liveuser',
                            InitialSetupEnable='False', TimedLoginEnable='False')
    config['daemon'].pop('TimedLogin', None)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as stream:
        config.write(stream)
    # A passwordless disposable session must not get stuck at a lock screen.
    profile = root / 'etc/dconf/profile/user'
    profile.parent.mkdir(parents=True, exist_ok=True)
    previous = profile.read_text() if profile.exists() else 'user-db:user\nsystem-db:local\n'
    if 'system-db:azurefin-live' not in previous.splitlines():
        profile.write_text(previous.rstrip() + '\nsystem-db:azurefin-live\n')
    settings = root / 'etc/dconf/db/azurefin-live.d'
    (settings / 'locks').mkdir(parents=True, exist_ok=True)
    (settings / '00-session').write_text(
        '[org/gnome/desktop/screensaver]\nlock-enabled=false\n'
        '[org/gnome/desktop/lockdown]\ndisable-lock-screen=true\n')
    (settings / 'locks/session').write_text(
        '/org/gnome/desktop/screensaver/lock-enabled\n'
        '/org/gnome/desktop/lockdown/disable-lock-screen\n')
    run('dconf', 'update')


if __name__ == '__main__':
    configure()
