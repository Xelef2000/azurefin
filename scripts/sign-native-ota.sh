#!/usr/bin/env bash
# Additional native-container signature. Keep the keyless release signature.
set -euo pipefail
: "${AZUREFIN_OTA_SIGNING_KEY:?}" "${COSIGN_PASSWORD:?}" "${RELEASE_TAG:?}"
: "${GHCR_TOKEN:?}" "${REGISTRY_OWNER:?}" "${RUNNER_TEMP:?}"
[[ "$RELEASE_TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-alpha)?$ ]]
[[ $# == 1 && "$1" =~ ^ghcr\.io/xelef2000/azurefin@sha256:[a-f0-9]{64}$ ]]
reference=$1
# Catch a mismatched secret/public-key pair before publishing any signature.
diff -u surface/ota-signing.pub <(cosign public-key --key env://AZUREFIN_OTA_SIGNING_KEY)
# The publication step logs out on exit. Authenticate this step independently.
export DOCKER_CONFIG
DOCKER_CONFIG=$(mktemp -d "$RUNNER_TEMP/azurefin-native-auth.XXXXXXXX")
trap 'rm -f -- "$DOCKER_CONFIG/config.json"; rmdir -- "$DOCKER_CONFIG"' EXIT
printf '%s' "$GHCR_TOKEN" | cosign login ghcr.io -u "$REGISTRY_OWNER" --password-stdin
unset GHCR_TOKEN
# containers/image consumes legacy sigstore attachments, not Cosign 3 bundles.
# The production native key is used ONLY for audited, bootable base images.
cosign sign --yes --key env://AZUREFIN_OTA_SIGNING_KEY \
    --new-bundle-format=false --use-signing-config=false \
    -a "release=$RELEASE_TAG" -a component=base "$reference"
cosign verify --key surface/ota-signing.pub --new-bundle-format=false \
    -a "release=$RELEASE_TAG" -a component=base "$reference" \
    > release-metadata/base-native-signature.json
