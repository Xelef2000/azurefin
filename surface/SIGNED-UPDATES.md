# Signed OS updates

Implementation status: development/testing. Signed tag-only candidates have
been tested on hardware with the private-image updater. Alpha 3 predates this updater and cannot use
these commands without a reviewed bootstrap migration. Do not unmask the stock
bootc update timer or switch a firmware-enabled installation to the public base.

## Trust boundary

Release CI audits the public base and installer before publishing. It signs
each immutable digest with Cosign 3 / Sigstore keyless signing, using GitHub's
OIDC issuer. This keyless path does not require a long-lived private key.
Signing and verification failures fail the release job.

### Native bootc signature integration (not yet deployed)

The native verifier cannot currently match GitHub Actions' Fulcio URI identity.
The proposed release workflow therefore adds a second, public-key signature to
the audited **base only**, retaining the existing keyless signatures on both
base and installer. `surface/ota-signing.pub` is the native trust anchor;
`cosign.pub` is unrelated and is not replaced. The native key must never sign
installer images, development builds or non-bootable test fixtures.

The encrypted private key and password are repository Actions secrets named
`AZUREFIN_OTA_SIGNING_KEY` and `AZUREFIN_OTA_SIGNING_PASSWORD`. These are repository
secrets, not a separately approval-protected GitHub environment: repository and
workflow write access are part of the signing trust boundary. Only the tagged
release signing step receives them. Maintain a restricted offline backup and
review workflow changes before allowing a release to use the key.

Public-key fingerprint (SHA-256 of DER SubjectPublicKeyInfo):
`c784e8b27ac8400842a580c9a8e6bb1c123555ca37812641365b69c0a18fbd65`.

Cosign 3.1.4 uses legacy attachments for this additional signature because that
is the format consumed by containers/image. Transparency logging and Cosign's
verification remain enabled. Native public-key policy authenticates the key,
digest and repository; it does **not** enforce our release/component annotations
or prevent replay of an older valid image. Do not describe it as release-tag
freshness enforcement. Key rotation needs an overlap release trusting both
public keys before switching signers; compromise requires explicit recovery
and removal of the compromised key, not merely generating another key.

`scripts/test-native-signatures.py` passes offline acceptance and rejection
tests. The manual registry test uses disposable keys and anonymous reads;
it must pass before production signing is enabled in a merged workflow.
No native policy or public-key trust has been installed on the Surface, and
automatic bootc updates remain disabled pending end-to-end migration tests.

`azurefin-update` accepts only `ghcr.io/xelef2000/azurefin`, the exact
`release-romulus.yml@refs/tags/VERSION` certificate identity, GitHub's OIDC
issuer, and signed `release=VERSION` / `component=base` annotations. An installer
signature, another workflow, an unsigned image or another release must fail.
Cosign's transparency-log and certificate checks remain enabled. The manifest
is resolved once and all later downloads use its verified digest.

The public signature authenticates the base, **not** the locally modified OS.
The verified base supplies its own provisioning tools and firmware policy.
The local build checks the MSI and extracted firmware, rebuilds the initramfs,
then stages a private OCI deployment using bootc. A root-owned receipt records
the verified base digest and release beside that deployment. Local root and
the existing installed updater are trusted; this is not Secure Boot, protection
against local root, or an independent signature on the private deployment.

Release numbers are explicitly selected. This first version does not discover
updates automatically, enforce monotonic version numbers, or protect against
an administrator explicitly selecting an older signed release. There is no
unsigned fallback and no floating `latest` channel.

## Using a future signed release

Check authenticity without changing deployments:

```sh
azurefin-update --release v0.0.4-alpha --check
```

The version above is an example, not a claim that this release exists.
Prepare and stage an update, reusing an MSI you have or downloading it again:

```sh
sudo azurefin-update --release v0.0.4-alpha --download --stage
# Or: --msi /path/to/supported.msi instead of --download
```

Without `--stage`, only preparation happens. No automatic reboot occurs.
Keep the charger connected and at least 60 GiB free during this initial
implementation; separate download/import and firmware workspaces are retained
under `/var/lib/azurefin/provisioning` for diagnosis. This is intentionally not
yet a space-optimized background updater. Firmware is never uploaded. Existing
Bluetooth configuration in `/etc` is not overwritten by the update tool.

## Before enabling OTA for users

- [ ] Review and merge the implementation; publish a signed test release.
- [x] Verify real valid and unsigned images, wrong identity/issuer/claims,
      substituted tags, and digest-preserving OCI downloads (manual CI fixtures).
- [ ] Test firmware rebuilding/staging in a VM and on the Surface, including
      LUKS unlock, input, Wi-Fi, audio safety settings and Bluetooth retention.
- [ ] Test interrupted downloads/builds and rollback to the previous deployment.
- [ ] Provide a reviewed one-time bootstrap for existing alpha 3 installations.
- [ ] Optimize workspace reuse and retain verified firmware for offline reuse.
- [ ] Only then add update discovery, channel/freshness policy and scheduling.

Prebuilt-tested-ISO releases remain excluded by the existing release marker.
Do not re-sign alpha 3 as if it had been produced by this new workflow.

### Tag-only candidate builds

After reviewing and merging the workflow changes, a maintainer may explicitly
create a new version tag and manually dispatch `release-romulus.yml` at that
tag. Branch dispatches are skipped. This uses the same release-tag signing
identity as the eventual release, but creates no GitHub release or ISO.
The ISO workflow ignores manually dispatched candidate builds. Both workflow
changes must be on the default branch before using this path, because GitHub
loads the downstream `workflow_run` policy from that branch.

Creating a candidate tag and publishing its images requires explicit maintainer
approval. A successfully signed candidate still requires boot/update testing;
do not treat it as a validated public release. Do not move a published signed
candidate tag to different code: corrections need a new version.

## Validation evidence (2026-10-27)

- [Manual signature run](https://github.com/Xelef2000/azurefin/actions/runs/40506105875)
  passed using two tiny, non-bootable GHCR fixtures. Negative-case logs showed
  the expected signature, identity and annotation failures, not network errors.
  These test-workflow signatures are explicitly rejected under the production
  release-workflow identity.
- Anonymous GHCR reads and Cosign verification were independently confirmed
  after the container package was made public. CI credentials alone are not
  sufficient evidence that installed systems can download updates.
- Local ARM64 base `ac9270c0b8f552b104e7315f85efaa9de5e0725987ea24583fb027b614d89f27`
  built successfully; updater help, Cosign, Skopeo and bootc ran in the image.
  All 82 OCI layers passed the release-content audit. Automatic bootc updates
  remain masked. This local image is not a signed release.
- Its two lint warnings came from `/var/log/dnf5.log.1`. The updated cleanup
  removed only DNF log rotations in a disposable container; lint then passed
  14 checks, skipped one, and reported no warnings. A rebuilt image is still
  required to include that cleanup change.
- The ARM64 image's Cosign binary verified the public test signature and rejected
  it under the production release identity, without registry credentials.
- Local offline firmware preparation completed using tools exported from that
  audited base. MSI/extracted-file verification, initramfs preflight and final
  verification, and OCI export passed. Result:
  `2ce18443d7e3291825a90f6f8610e8bd502d594bb5d0c2aeeadcf463b4a7291e`,
  labelled `locally-provisioned-do-not-publish`. Nothing was staged or uploaded.
  This used the pre-cleanup base and retained its DNF log warning plus the known
  root-cache tmpfiles warning. It is a preparation test, not an end-to-end signed
  release deployment or successful boot/rollback test.

References: [Cosign verification](https://github.com/sigstore/cosign/blob/main/doc/cosign_verify.md)
and [bootc security model](https://bootc.dev/bootc/bootc-security.7.html).
