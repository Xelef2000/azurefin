#!/usr/bin/env bash
set -euo pipefail

echo "=== Building iptsd from source (alex-lentz fork) ==="

dnf install -y \
    git \
    gcc \
    gcc-c++ \
    meson \
    ninja-build \
    cmake \
    systemd-devel \
    libevdev-devel \
    inih-devel \
    cli11-devel \
    spdlog-devel \
    eigen3-devel \
    fmt-devel \
    SDL2-devel

TMPDIR="/tmp/iptsd-build"
mkdir -p "$TMPDIR"
cd "$TMPDIR"

git clone --depth=1 https://github.com/alex-lentz/iptsd.git
cd iptsd

meson setup build --prefix=/usr
meson compile -C build
meson install -C build

systemctl enable iptsd.service 2>/dev/null || true

cd /
rm -rf "$TMPDIR"
dnf remove -y meson ninja-build cmake cli11-devel spdlog-devel \
    eigen3-devel fmt-devel 2>/dev/null || true
dnf clean all

echo "=== iptsd build complete ==="
