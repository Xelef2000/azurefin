#!/usr/bin/env bash
# Called only by the manual fixture job. NEVER uses the production OTA key.
set -euo pipefail
[[ ${GITHUB_ACTIONS:-false} == true && ${GITHUB_EVENT_NAME:-} == workflow_dispatch ]]
[[ $# == 2 ]]
signed=$1
unsigned=$2
[[ "$signed" =~ ^ghcr\.io/[a-z0-9/._-]+@sha256:[a-f0-9]{64}$ ]]
[[ "$unsigned" =~ ^ghcr\.io/[a-z0-9/._-]+@sha256:[a-f0-9]{64}$ ]]
work=$(mktemp -d "$RUNNER_TEMP/azurefin-native-test.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
umask 077
export COSIGN_PASSWORD=disposable-test-only
for name in trusted wrong; do
    (cd "$work" && cosign generate-key-pair --output-key-prefix "$name")
done
cosign sign --yes --key "$work/trusted.key" --new-bundle-format=false \
    --use-signing-config=false -a component=non-bootable-test "$signed"
export NATIVE_TEST_WORK="$work" NATIVE_TEST_REPOSITORY="${signed%@*}"
python3 - <<'PY'
import json
import os
from pathlib import Path
root = Path(os.environ['NATIVE_TEST_WORK'])
repository = os.environ['NATIVE_TEST_REPOSITORY']
(root / 'registries').mkdir()
(root / 'registries' / 'test.yaml').write_text(
    'docker:\n  ' + repository + ':\n    use-sigstore-attachments: true\n')
for name, key, identity in [('trusted', 'trusted', repository),
                            ('wrong-key', 'wrong', repository),
                            ('wrong-repository', 'trusted', 'example.invalid/other/image')]:
    policy = {'default': [{'type': 'reject'}], 'transports': {'docker': {
        repository: [{'type': 'sigstoreSigned', 'keyPath': str(root / (key + '.pub')),
                      'signedIdentity': {'type': 'exactRepository', 'dockerRepository': identity}}]}}}
    (root / (name + '.json')).write_text(json.dumps(policy))
PY
verify() {
    local policy=$1 reference=$2 destination=$3
    skopeo --registries.d "$work/registries" --policy "$work/$policy.json" \
        copy --src-no-creds --remove-signatures "docker://$reference" "dir:$work/$destination"
}
verify trusted "$signed" accepted > ota-signature-results/native-valid.log 2>&1
for name in unsigned wrong-key wrong-repository; do
    reference=$signed
    policy=$name
    if [[ "$name" == unsigned ]]; then reference=$unsigned; policy=trusted; fi
    log="ota-signature-results/native-$name.log"
    if verify "$policy" "$reference" "rejected-$name" > "$log" 2>&1; then
        echo "SECURITY TEST FAILED: native verifier accepted $name" >&2
        exit 1
    fi
    # Network/authentication failures do not count as signature rejection.
    grep -q 'Source image rejected' "$log"
done
echo NATIVE_REGISTRY_SIGNATURE_TEST_PASSED | tee ota-signature-results/native-result.txt
