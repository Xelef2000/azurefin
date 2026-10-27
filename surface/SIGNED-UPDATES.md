# Signed OS updates

Implementation status: development/testing. No signed OTA release has yet been
published or tested on hardware. Alpha 3 predates this updater and cannot use
these commands without a reviewed bootstrap migration. Do not unmask the stock
bootc update timer or switch a firmware-enabled installation to the public base.

## Trust boundary

Release CI audits the public base and installer before publishing. It signs
each immutable digest with Cosign 3 / Sigstore keyless signing, using GitHub's
OIDC issuer. No long-lived signing private key or new repository secret is
needed. Signing and verification failures fail the release job.

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
- [ ] Verify actual valid, unsigned, wrong-identity and tampered image cases,
      not just command orchestration tests.
- [ ] Test firmware rebuilding/staging in a VM and on the Surface, including
      LUKS unlock, input, Wi-Fi, audio safety settings and Bluetooth retention.
- [ ] Test interrupted downloads/builds and rollback to the previous deployment.
- [ ] Provide a reviewed one-time bootstrap for existing alpha 3 installations.
- [ ] Optimize workspace reuse and retain verified firmware for offline reuse.
- [ ] Only then add update discovery, channel/freshness policy and scheduling.

Prebuilt-tested-ISO releases remain excluded by the existing release marker.
Do not re-sign alpha 3 as if it had been produced by this new workflow.

References: [Cosign verification](https://github.com/sigstore/cosign/blob/main/doc/cosign_verify.md)
and [bootc security model](https://bootc.dev/bootc/bootc-security.7.html).
