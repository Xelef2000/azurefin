# vim: set ft=make :
##############################
### Surface Laptop 7 commands
##############################

# Rebuild initramfs
[group('Surface')]
rebuild-initramfs:
    #!/usr/bin/bash
    sudo dracut --regenerate-all --force
    echo "Initramfs rebuilt. Reboot to apply changes."

# Reset the embedded controller (fixes stuck trackpad/keyboard)
[group('Surface')]
ec-reboot:
    #!/usr/bin/bash
    echo "Resetting the Surface embedded controller..."
    sudo /usr/local/bin/ec-reboot

