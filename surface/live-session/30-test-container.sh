#!/usr/bin/env bash
# No networking, devices, privileged mode, host services or writable host mounts.
set -euo pipefail
test_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
image=${1:-localhost/azurefin:postinstall-bootstrap}
if (($#)); then shift; fi
podman run --rm --pull=never --network=none \
    --volume "$test_dir:/tests:ro,Z" \
    --entrypoint /usr/bin/python3 "$image" /tests/test_container.py "$@"
