#!/usr/bin/env bash
# Promote an existing signed base; never build or sign anything here.
set -euo pipefail
: "${RELEASE_TAG:?}" "${IMAGE_DIGEST:?}" "${EXPECTED_CURRENT:?}"
: "${GHCR_TOKEN:?}" "${RUNNER_TEMP:?}" "${GITHUB_ACTOR:?}"
[[ "$RELEASE_TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-alpha)?$ ]]
[[ "$IMAGE_DIGEST" =~ ^sha256:[a-f0-9]{64}$ ]]
[[ "$EXPECTED_CURRENT" == absent || "$EXPECTED_CURRENT" =~ ^sha256:[a-f0-9]{64}$ ]]
repository=ghcr.io/xelef2000/azurefin
reference="$repository@$IMAGE_DIGEST"
mkdir -p promotion-results

# Both checks bind the immutable manifest to the requested base release.
cosign verify \
    --certificate-identity "https://github.com/Xelef2000/azurefin/.github/workflows/release-romulus.yml@refs/tags/$RELEASE_TAG" \
    --certificate-oidc-issuer https://token.actions.githubusercontent.com \
    -a "release=$RELEASE_TAG" -a component=base "$reference" \
    > promotion-results/keyless.json
cosign verify --key surface/ota-signing.pub --new-bundle-format=false \
    -a "release=$RELEASE_TAG" -a component=base "$reference" \
    > promotion-results/native.json

# The digest and release claims were verified above. Only promote images with
# the firmware contract supported by existing installations on this channel.
skopeo inspect --no-creds --config "docker://$reference" > promotion-results/config.json
python3 scripts/check-update-contract.py promotion-results/config.json surface/update-contract.json

# Fail on registry errors, rather than treating them as a missing channel.
skopeo list-tags --no-creds "docker://$repository" > promotion-results/tags-before.json
current=absent
has_testing=$(python3 -c 'import json; print("testing" in json.load(open("promotion-results/tags-before.json"))["Tags"])')
if [[ "$has_testing" == True ]]; then
    current=$(skopeo inspect --no-creds --format '{{.Digest}}' "docker://$repository:testing")
fi
[[ "$current" == "$EXPECTED_CURRENT" ]] || {
    printf 'Channel changed: expected %s, found %s\n' "$EXPECTED_CURRENT" "$current" >&2
    exit 1
}
printf '%s\n' "$current" > promotion-results/previous-digest.txt

auth_dir=$(mktemp -d "$RUNNER_TEMP/azurefin-promotion-auth.XXXXXXXX")
trap 'rm -f -- "$auth_dir/auth.json"; rmdir -- "$auth_dir"' EXIT
printf '%s' "$GHCR_TOKEN" | skopeo login --authfile "$auth_dir/auth.json" \
    --username "$GITHUB_ACTOR" --password-stdin ghcr.io
unset GHCR_TOKEN
# Signatures are digest-addressed in this same repository and remain unchanged.
# --remove-signatures avoids copying them as transport-specific image metadata;
# it does not remove the existing registry signature attachments.
skopeo copy --src-no-creds --dest-authfile "$auth_dir/auth.json" \
    --preserve-digests --remove-signatures "docker://$reference" "docker://$repository:testing"
published=$(skopeo inspect --no-creds --format '{{.Digest}}' "docker://$repository:testing")
[[ "$published" == "$IMAGE_DIGEST" ]]
printf '%s\n' "$published" > promotion-results/published-digest.txt
cosign verify --key surface/ota-signing.pub --new-bundle-format=false \
    -a "release=$RELEASE_TAG" -a component=base "$repository:testing" \
    > promotion-results/channel-native.json
