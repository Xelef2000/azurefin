#!/usr/bin/env bash
set -euo pipefail

echo "=== Building ELLX kernel for Surface Laptop 7 ==="

dnf install -y \
    git \
    gcc \
    make \
    flex \
    bison \
    bc \
    openssl-devel \
    elfutils-devel \
    elfutils-libelf-devel \
    dwarves \
    dtc \
    dracut \
    perl \
    python3 \
    diffutils \
    findutils \
    ncurses-devel \
    rsync \
    kmod \
    cpio \
    xz \
    zstd

# When building on x86_64 (QEMU not set up), the host gcc doesn't understand
# arm64-specific flags like -mlittle-endian. Install the cross-compiler.
HOST_ARCH=$(uname -m)
CROSS_COMPILE_PREFIX=""
if [ "$HOST_ARCH" != "aarch64" ]; then
    echo "Host is ${HOST_ARCH} — installing aarch64 cross-compiler..."
    dnf install -y gcc-aarch64-linux-gnu
    CROSS_COMPILE_PREFIX="aarch64-linux-gnu-"
fi

# All make invocations share these args
KBUILD=(ARCH=arm64)
[ -n "$CROSS_COMPILE_PREFIX" ] && KBUILD+=(CROSS_COMPILE="$CROSS_COMPILE_PREFIX")

KERNEL_WORKDIR="/tmp/kernel-build"
mkdir -p "$KERNEL_WORKDIR"
cd "$KERNEL_WORKDIR"

git clone --depth=1 --branch 7.0-sl7 \
    https://github.com/ProgrammerIn-wonderland/ELLX-Kernel.git linux
cd linux

# Apply any local patches
if [ -d /ctx/kernel/patches ]; then
    for patch in /ctx/kernel/patches/*.patch; do
        [ -f "$patch" ] || continue
        echo "Applying patch: $(basename "$patch")"
        git apply "$patch" || echo "WARNING: patch $(basename "$patch") did not apply cleanly"
    done
fi

make "${KBUILD[@]}" defconfig

scripts/config --enable CONFIG_ARCH_QCOM
scripts/config --enable CONFIG_DRM_MSM
scripts/config --enable CONFIG_ATH12K
scripts/config --enable CONFIG_ATH12K_PCI
scripts/config --enable CONFIG_HID_MULTITOUCH
scripts/config --enable CONFIG_I2C_HID_OF
scripts/config --enable CONFIG_I2C_QCOM_GENI
scripts/config --enable CONFIG_SPI_QCOM_GENI
scripts/config --enable CONFIG_QCOM_PDC
scripts/config --enable CONFIG_PINCTRL_X1E80100
scripts/config --enable CONFIG_QCOM_SCM
scripts/config --enable CONFIG_QRTR
scripts/config --enable CONFIG_QRTR_MHI
scripts/config --enable CONFIG_MHI_BUS
scripts/config --enable CONFIG_MHI_BUS_PCI_GENERIC
scripts/config --enable CONFIG_REMOTEPROC
scripts/config --enable CONFIG_QCOM_Q6V5_PAS
scripts/config --enable CONFIG_QCOM_FASTRPC
scripts/config --enable CONFIG_SOUNDWIRE
scripts/config --enable CONFIG_SND_SOC_QCOM
scripts/config --enable CONFIG_BATTERY_QCOM_BATTMGR
scripts/config --enable CONFIG_USB_DWC3
scripts/config --enable CONFIG_USB_DWC3_QCOM
scripts/config --enable CONFIG_TYPEC
scripts/config --enable CONFIG_TYPEC_UCSI
scripts/config --enable CONFIG_PHY_QCOM_QMP_COMBO
scripts/config --enable CONFIG_PHY_QCOM_QMP_USB
scripts/config --enable CONFIG_QCOM_RPMH
scripts/config --enable CONFIG_INTERCONNECT_QCOM
scripts/config --enable CONFIG_QCOM_COMMAND_DB
scripts/config --enable CONFIG_QCOM_AOSS_QMP
scripts/config --enable CONFIG_ARM_QCOM_CPUFREQ_HW
scripts/config --enable CONFIG_CPU_FREQ_GOV_SCHEDUTIL
scripts/config --set-str CONFIG_LOCALVERSION "-surface-sl7"

make "${KBUILD[@]}" olddefconfig

NPROCS=$(nproc)
echo "Building kernel Image and modules with $NPROCS cores..."

BUILD_LOG="/tmp/kernel-build.log"
if ! make "${KBUILD[@]}" -j"$NPROCS" Image.gz modules 2>&1 | tee "$BUILD_LOG"; then
    echo ""
    echo "=== KERNEL BUILD FAILED — errors ==="
    grep -i "error:" "$BUILD_LOG" | grep -v "^In file\|note:" | tail -30 || tail -40 "$BUILD_LOG"
    exit 1
fi

# Build x1e80100 DTBs that actually exist in this branch (no el2 overlays).
# Discover from source rather than hardcoding names — the ELLX branch may not
# have the same romulus13/romulus15 split as mainline.
echo "Building x1e80100 DTBs (skipping el2 overlays)..."
while IFS= read -r dts; do
    # Kernel DTS Makefile expects the target relative to arch/arm64/boot/dts/,
    # not the full path from the kernel root — passing the full path causes it
    # to double-prepend arch/arm64/boot/dts/ and fail with "no rule to make target".
    rel="${dts#arch/arm64/boot/dts/}"
    dtb="${rel%.dts}.dtb"
    make "${KBUILD[@]}" "$dtb" 2>&1 \
        && echo "  Built: $(basename "$dtb")" \
        || echo "  WARNING: failed to build $(basename "$dtb"), skipping"
done < <(find arch/arm64/boot/dts/qcom -name "x1e80100*.dts" ! -name "*-el2.dts" | sort)

# --- Direct installation (no RPM) ---
# Installing kernel RPMs via dnf inside a container build triggers the
# 05-rpmostree.install kernel-install hook, which calls systemctl — unavailable
# in the container build environment. Install files directly instead.

# kernelrelease includes LOCALVERSION and git hash (e.g. 7.0.0-rc3-surface-sl7-gb67c4f9b1299)
# kernelversion only returns the base number (7.0.0-rc3) — modules are NOT installed there
KVER="$(make "${KBUILD[@]}" -s kernelrelease)"
echo "Installing kernel ${KVER} directly..."

# Modules
make "${KBUILD[@]}" modules_install

# Kernel image, symbol map, config
mkdir -p /boot
install -m0755 arch/arm64/boot/Image.gz "/boot/vmlinuz-${KVER}"
install -m0644 System.map              "/boot/System.map-${KVER}"
install -m0644 .config                 "/boot/config-${KVER}"

# DTBs
mkdir -p "/boot/dtb-${KVER}/qcom"
if ls arch/arm64/boot/dts/qcom/x1e80100*.dtb 1>/dev/null 2>&1; then
    cp arch/arm64/boot/dts/qcom/x1e80100*.dtb "/boot/dtb-${KVER}/qcom/"
    echo "  DTBs installed to /boot/dtb-${KVER}/qcom/"
else
    echo "  WARNING: no x1e80100 DTBs found — UEFI firmware will need to supply the DTB"
fi

# Initramfs
echo "Generating initramfs for ${KVER}..."
dracut --force "/boot/initramfs-${KVER}.img" "${KVER}"

echo "Kernel ${KVER} installed."

# --- Out-of-tree modules ---
# Build against the source tree now, before it is deleted.
# DKMS is not used — on a bootc image the kernel only changes via image
# rebuilds, so there is nothing to trigger a DKMS rebuild at runtime.

echo "Building cpu-parking module..."
MODTMP="/tmp/cpu-parking-build"
cp -r /ctx/custom/usr/src/cpu-parking "$MODTMP"
make -C "$KERNEL_WORKDIR/linux" "${KBUILD[@]}" M="$MODTMP" modules
INSTALL_MOD_PATH="/" make -C "$KERNEL_WORKDIR/linux" "${KBUILD[@]}" M="$MODTMP" modules_install
echo "cpu_parking" > /etc/modules-load.d/cpu-parking.conf
rm -rf "$MODTMP"
echo "  cpu-parking module installed for ${KVER}."

# --- Cleanup ---
cd /
rm -rf "$KERNEL_WORKDIR"
dnf remove -y git gcc make flex bison bc openssl-devel dtc \
    elfutils-devel elfutils-libelf-devel dwarves ncurses-devel \
    gcc-aarch64-linux-gnu 2>/dev/null || true
dnf clean all

echo "=== Kernel build complete ==="
