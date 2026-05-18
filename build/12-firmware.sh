#!/usr/bin/env bash
set -euo pipefail

echo "=== Downloading and installing Surface Laptop 7 firmware ==="

# --- Dependencies ---
dnf5 install -y msitools curl python3

# --- Configuration ---
MSI_URL="https://download.microsoft.com/download/b7ca2c3f-d320-4795-be0f-529a0117abb4/SurfaceLaptop7_ARM_Win11_26100_26.011.9344.0.msi"
FW_BASE="/lib/firmware/qcom/x1e80100/microsoft"
FW_ROMULUS="${FW_BASE}/Romulus"

# All 11 files present in both microsoft/ and microsoft/Romulus/ in the MSI
FIRMWARE_FILES=(
    adsp_dtbs.elf adspr.jsn adsps.jsn adspua.jsn battmgr.jsn
    cdsp_dtbs.elf cdspr.jsn qcadsp8380.mbn qccdsp8380.mbn
    qcdxkmsuc8380.mbn qcdxkmsucpurwa.mbn
)
# WiFi/BT blobs that may or may not be present depending on MSI version
OPTIONAL_FIRMWARE_FILES=(
    qcwlan8380.mbn qcwlan8380_pci.mbn qcbtfw8380.mbn
)

WORKDIR="/tmp/firmware-build"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

# --- Download MSI from Microsoft ---
echo "[1/6] Downloading Surface Laptop 7 firmware MSI from Microsoft..."
curl -L --retry 3 --retry-delay 5 -o surface.msi "$MSI_URL"

# --- Extract MSI ---
echo "[2/6] Extracting MSI package..."
mkdir -p extracted
msiextract -C extracted surface.msi

# --- Install firmware files ---
echo "[3/6] Installing firmware files into image..."
mkdir -p "$FW_BASE" "$FW_ROMULUS"

install_fw() {
    local dest="$1"
    local required="$2"
    shift 2
    local found=0 missing=0
    for fw in "$@"; do
        match=$(find extracted -name "$fw" -print -quit 2>/dev/null)
        if [ -n "$match" ]; then
            cp "$match" "${dest}/"
            echo "  Installed: ${dest##*/lib/firmware/}/$fw"
            found=$((found + 1))
        else
            [ "$required" = "required" ] && echo "  MISSING:   $fw" || echo "  Optional:  $fw (not found)"
            missing=$((missing + 1))
        fi
    done
    echo "  → $found installed, $missing not found"
}

echo "  Installing to ${FW_BASE}..."
install_fw "$FW_BASE" required "${FIRMWARE_FILES[@]}"
install_fw "$FW_BASE" optional "${OPTIONAL_FIRMWARE_FILES[@]}"

echo "  Installing to ${FW_ROMULUS}..."
install_fw "$FW_ROMULUS" required "${FIRMWARE_FILES[@]}"
install_fw "$FW_ROMULUS" optional "${OPTIONAL_FIRMWARE_FILES[@]}"

# --- WiFi board-2.bin fix ---
echo "[4/6] Downloading board-2.bin from Qualcomm upstream..."
BOARD_URL="https://git.codelinaro.org/clo/ath-firmware/ath12k-firmware/-/raw/main/WCN7850/hw2.0/board-2.bin?ref_type=heads"
BDENCODER_URL="https://raw.githubusercontent.com/qca/qca-swiss-army-knife/master/tools/scripts/ath12k/ath12k-bdencoder"
BOARD_DIR="/lib/firmware/ath12k/WCN7850/hw2.0"

mkdir -p board-fix
cd board-fix
curl -L --retry 3 -o board-2.bin "$BOARD_URL"
curl -L --retry 3 -o ath12k-bdencoder "$BDENCODER_URL"
chmod +x ath12k-bdencoder

echo "[5/6] Patching board-2.bin with Surface Laptop 7 device ID..."
./ath12k-bdencoder -e board-2.bin

python3 <<'PY'
import json, sys

match_name = "bus=pci,vendor=17cb,device=1107,subsystem-vendor=17cb,subsystem-device=3378,qmi-chip-id=2,qmi-board-id=255"
new_name   = "bus=pci,vendor=17cb,device=1107,subsystem-vendor=17cb,subsystem-device=1107,qmi-chip-id=2,qmi-board-id=255"

with open("board-2.json", "r") as f:
    data = json.load(f)

if not isinstance(data, list):
    print("ERROR: unexpected JSON structure", file=sys.stderr)
    sys.exit(1)

found = False
already_present = False
for group in data:
    if not isinstance(group, dict):
        continue
    for entry in group.get("board", []):
        names = entry.get("names", [])
        if match_name in names:
            found = True
            if new_name in names:
                already_present = True
            else:
                names.append(new_name)
            break
    if found:
        break

if not found:
    print("WARNING: Target board entry not found — board-2.bin format may have changed.", file=sys.stderr)
    print("WiFi may not work without this fix.", file=sys.stderr)
    sys.exit(0)

if already_present:
    print("  Surface Laptop 7 device ID already present, no change needed.")
else:
    with open("board-2.json", "w") as f:
        json.dump(data, f, indent=4)
        f.write("\n")
    print("  Added Surface Laptop 7 device ID to board-2.bin")
PY

./ath12k-bdencoder -c board-2.json

echo "[6/6] Installing patched board-2.bin..."
mkdir -p "$BOARD_DIR"
cp board-2.bin "$BOARD_DIR/board-2.bin"

# --- Cleanup ---
cd /
rm -rf "$WORKDIR"
dnf5 clean all

echo "=== Firmware installation complete ==="
