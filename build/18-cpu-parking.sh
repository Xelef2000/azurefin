#!/usr/bin/env bash
set -euo pipefail

# cpu-parking out-of-tree module is built inside 15-kernel.sh while the
# kernel source tree is still present, before it is cleaned up.
# Nothing to do here.
echo "=== cpu-parking module already built by 15-kernel.sh — skipping ==="
