# Based on projectbluefin/common's update.just; bootc remains the OS updater.
alias upgrade := update

# Update the OS, Flatpak applications and Homebrew. Reboot separately when ready.
update:
    #!/usr/bin/bash
    set -euo pipefail
    if systemctl is-active --quiet uupd.service; then
        echo 'Automatic updates are running; check journalctl -u uupd.service.'
        exit 1
    fi
    # Share the firmware setup lock; do not provision concurrently with staging.
    sudo flock --nonblock /var/lib/azurefin/firmware-store.lock /usr/bin/bash -ec \
        'python3 /usr/libexec/azurefin/system_update_preflight.py && bootc upgrade'
    flatpak update --system -y
    flatpak update --user -y
    if [[ -O /home/linuxbrew/.linuxbrew/bin/brew ]]; then
        /home/linuxbrew/.linuxbrew/bin/brew upgrade
    fi
    echo 'Update complete. Reboot when convenient to apply a staged OS update.'
