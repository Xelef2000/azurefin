#!/usr/bin/python3
"""Launch interactive Anaconda from the disposable GNOME session only."""
import os
import pwd
from pathlib import Path
import subprocess


def run(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True)


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Launch using the Install Azurefin application')
    if 'azurefin.live=1' not in Path('/proc/cmdline').read_text().split():
        raise RuntimeError('Installer launcher is only available on live media')
    if run('findmnt', '-n', '-o', 'FSTYPE', '-T', '/run/overlayfs').stdout.strip() != 'tmpfs':
        raise RuntimeError('Refusing to launch outside the disposable live session')
    media = Path('/run/initramfs/live')
    for name in ('base-oci/index.json', 'base-oci/oci-layout', 'base-image-id', 'support'):
        if not (media / 'azurefin' / name).exists():
            raise RuntimeError(f'Installation media is missing azurefin/{name}')
    # Keep the existing, tested kickstart paths. Never copy the live filesystem
    # into the installed system; Anaconda deploys the separate OCI payload.
    repo = Path('/run/install/repo')
    repo.mkdir(parents=True, exist_ok=True)
    if subprocess.run(['mountpoint', '-q', str(repo)]).returncode != 0:
        run('mount', '--bind', str(media), str(repo))
        run('mount', '-o', 'remount,bind,ro', str(repo))
    if not os.environ.get('WAYLAND_DISPLAY') or not os.environ.get('XDG_RUNTIME_DIR'):
        raise RuntimeError('Start Install Azurefin from the live GNOME desktop')
    # Anaconda temporarily switches EUID for the user's screensaver DBus call.
    # Its upstream helper uses the pkexec variable even when launched via sudo.
    uid = str(pwd.getpwnam('liveuser').pw_uid)
    if os.environ.get('SUDO_UID') != uid:
        raise RuntimeError('Launch the installer as liveuser via sudo')
    os.environ['PKEXEC_UID'] = uid
    # --liveinst uses interactive-defaults.ks, not --kickstart. It also selects
    # LIVE_OS behavior, so quitting the installer does not reboot the desktop.
    os.execv('/usr/bin/anaconda', ['anaconda', '--liveinst', '--graphical', '--noeject'])


if __name__ == '__main__':
    main()
