#!/usr/bin/env bash
# Additional native-container signature. Keep the keyless release signature.
set -euo pipefail
: "${AZUREFIN_OTA_SIGNING_KEY:?}" "${COSIGN_PASSWORD:?}" "${RELEASE_TAG:?}"
[[ "$RELEASE_TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-alpha)?$ ]]
[[ $# == 1 && "$1" =~ ^ghcr\.io/xelef2000/azurefin@sha256:[a-f0-9]{64}$ ]]
reference=$1
# Catch a mismatched secret/public-key pair before publishing any signature.
diff -u surface/ota-signing.pub <(cosign public-key --key env://AZUREFIN_OTA_SIGNING_KEY)
# containers/image consumes legacy sigstore attachments, not Cosign 3 bundles.
# The production native key is used ONLY for audited, bootable base images.
cosign sign --yes --key env://AZUREFIN_OTA_SIGNING_KEY \
    --new-bundle-format=false --use-signing-config=false \
    -a "release=$RELEASE_TAG" -a component=base "$reference"
cosign verify --key surface/ota-signing.pub --new-bundle-format=false \
    -a "release=$RELEASE_TAG" -a component=base "$reference" \
    > release-metadata/base-native-signature.json
