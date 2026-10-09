#!/usr/bin/env bash
# Select the single supported machine for OSTree's versioned boot deployment.
set -euo pipefail
root=${1:-/}
mapfile -t kernels < <(find "$root/usr/lib/modules" -mindepth 1 -maxdepth 1 -type d)
[[ ${#kernels[@]} -eq 1 && ${kernels[0]##*/} == *-azurefin.* ]] || {
    echo "Expected exactly one Azurefin kernel" >&2
    exit 1
}
kernel=${kernels[0]}
dtb="$kernel/dtb/qcom/x1e80100-microsoft-romulus13.dtb"
[[ $(od -An -tx1 -N4 "$dtb" | tr -d ' \n') == d00dfeed ]] || {
    echo "Missing or invalid Romulus13 device tree" >&2
    exit 1
}
# A single 'devicetree' makes OSTree emit an explicit BLS devicetree entry,
# instead of an fdtdir that depends on firmware-provided board selection.
install -m 0644 "$dtb" "$kernel/devicetree"
install -d -m 0755 "$root/usr/lib/bootc/kargs.d"
printf '%s\n' 'kargs = ["clk_ignore_unused", "pd_ignore_unused"]' \
    'match-architectures = ["aarch64"]' \
    > "$root/usr/lib/bootc/kargs.d/50-romulus.toml"
cmp "$dtb" "$kernel/devicetree"
echo INSTALLED_BOOT_INPUTS_PREPARED
