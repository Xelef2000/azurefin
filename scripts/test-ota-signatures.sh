#!/usr/bin/env bash
# Explicit manual CI test. Publishes only tiny scratch fixtures, never an OS.
set -euo pipefail
[[ ${GITHUB_ACTIONS:-false} == true && ${GITHUB_EVENT_NAME:-} == workflow_dispatch ]]
: "${GHCR_TOKEN:?}" "${GITHUB_REPOSITORY:?}" "${GITHUB_RUN_ID:?}" "${GITHUB_RUN_ATTEMPT:?}"
mkdir -p ota-signature-results
work=$(mktemp -d "$RUNNER_TEMP/azurefin-signatures.XXXXXXXX")
export DOCKER_CONFIG="$work/auth"
mkdir -m 0700 "$DOCKER_CONFIG"
printf '%s' "$GHCR_TOKEN" | podman login ghcr.io -u "$GITHUB_REPOSITORY_OWNER" --password-stdin
printf '%s' "$GHCR_TOKEN" | cosign login ghcr.io -u "$GITHUB_REPOSITORY_OWNER" --password-stdin
unset GHCR_TOKEN
trap 'podman logout ghcr.io' EXIT
repository="ghcr.io/${GITHUB_REPOSITORY,,}"
tag="ota-test-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
identity="https://github.com/$GITHUB_WORKFLOW_REF"
issuer=https://token.actions.githubusercontent.com
printf 'FROM scratch\nLABEL org.azurefin.test="non-bootable-signature-fixture"\n' > "$work/Containerfile"
podman build --platform linux/arm64 --label "test.nonce=$tag-signed" \
    -f "$work/Containerfile" -t "$repository:$tag-signed" "$work"
podman build --platform linux/arm64 --label "test.nonce=$tag-unsigned" \
    -f "$work/Containerfile" -t "$repository:$tag-unsigned" "$work"
podman push --digestfile ota-signature-results/signed.digest "$repository:$tag-signed"
podman push --digestfile ota-signature-results/unsigned.digest "$repository:$tag-unsigned"
signed="$repository@$(cat ota-signature-results/signed.digest)"
unsigned="$repository@$(cat ota-signature-results/unsigned.digest)"
[[ "$signed" != "$unsigned" ]]
cosign sign --yes -a release="$tag" -a component=base "$signed"
verify=(cosign verify --certificate-identity "$identity" --certificate-oidc-issuer "$issuer")
"${verify[@]}" -a release="$tag" -a component=base "$signed" > ota-signature-results/valid.json
reject() {
    local name=$1
    shift
    if "$@" > "ota-signature-results/$name.log" 2>&1; then
        echo "SECURITY TEST FAILED: accepted $name" >&2
        exit 1
    fi
    echo "Rejected: $name"
}
reject unsigned-image "${verify[@]}" "$unsigned"
reject wrong-release "${verify[@]}" -a release=wrong-release "$signed"
reject wrong-component "${verify[@]}" -a component=installer "$signed"
reject wrong-issuer cosign verify --certificate-identity "$identity" \
    --certificate-oidc-issuer https://invalid.example.test "$signed"
reject wrong-workflow cosign verify --certificate-identity \
    "https://github.com/$GITHUB_REPOSITORY/.github/workflows/not-authorized.yml@$GITHUB_REF" \
    --certificate-oidc-issuer "$issuer" "$signed"
reject production-identity cosign verify --certificate-identity \
    "https://github.com/$GITHUB_REPOSITORY/.github/workflows/release-romulus.yml@refs/tags/v0.0.4-alpha" \
    --certificate-oidc-issuer "$issuer" "$signed"
# Retarget only this run's disposable tag. The immutable signed digest stays valid.
podman tag "$repository:$tag-unsigned" "$repository:$tag-signed"
podman push "$repository:$tag-signed"
reject substituted-tag "${verify[@]}" -a release="$tag" "$repository:$tag-signed"
"${verify[@]}" -a release="$tag" -a component=base "$signed" > ota-signature-results/valid-after-retag.json
# Exercise the production digest-preserving downloader with a real OCI registry.
export OTA_TEST_REFERENCE="$signed" OTA_TEST_WORK="$work"
PYTHONPATH=surface python3 - <<'PY'
import json
import os
from pathlib import Path
import subprocess
import update
ref = os.environ['OTA_TEST_REFERENCE']
manifest = json.loads(subprocess.check_output(['skopeo', 'inspect', '--raw', 'docker://' + ref]))
update.fetch(Path(os.environ['OTA_TEST_WORK']), ref, manifest)
print('PRODUCTION_DIGEST_FETCH_PASSED')
PY
printf '%s\n' "$signed" "$unsigned" > ota-signature-results/references.txt
echo 'REAL_SIGNATURE_INTEGRATION_PASSED' | tee ota-signature-results/result.txt
