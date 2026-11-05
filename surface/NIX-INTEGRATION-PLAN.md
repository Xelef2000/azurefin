# Nix integration for Azurefin

Status: offline bootstrap, two-user sandbox builds, reboot persistence and
backing-path SELinux relabel validation passed in a disposable ARM64 VM.
Guarded initialization, full-store and forced-kill fault tests also passed.
Asynchronous systemd, repeat-boot, failure-isolated console login and per-user
preference tests passed. Fresh image, foreign-store refusal and encrypted-store
reboot tests passed on the earlier cached base. A newer-base repeat and
upgrade/rollback tests are in progress. Source/notice collection is reproducible
locally under `surface/nix/`; no upstream issue is required.
No production image integration or Surface deployment performed.
Date: 2026-11-05.

## Outcome

Provide multi-user Nix on installed Azurefin systems, initialized automatically
from a bundled offline payload. Keep composefs and the existing bootc update
model. Preserve administrator-editable global configuration and independent
per-user preferences.

Nix becomes ready after successful initialization on the first installed-system
boot, including the first boot after an existing device receives this feature.
Installing additional packages can still require network access.

## Agreed design

- Bake an empty, real `/nix` directory into every supported installed image.
- Bind-mount persistent `/var/lib/nix` at `/nix`.
- Keep `root.transient` disabled; no root remount, `chattr`, or initramfs change
  is required for this integration.
- Bundle a pinned NixOS community installer and the complete matching Nix
  bootstrap payload. Do not download an unpinned installer at runtime.
- Initialize once on the installed device, with safe recovery after interruption.
- Keep SELinux enforcing and support ordinary users through the Nix daemon.
- Preserve existing Nix installations; do not silently migrate or replace them.
- Let Azurefin own integration updates and Nix own its persistent runtime,
  profiles, and packages. OS rollback does not roll back Nix state.

## Filesystem and ownership

| Path | Owner and purpose |
| --- | --- |
| `/nix` | Image-owned empty mount point; mounted content is persistent |
| `/var/lib/nix` | Persistent store, database, profiles, and installer receipt |
| `/usr/share/azurefin/nix/` | Versioned installer, payload, checksums, and default-config reference |
| `/usr/libexec/azurefin/` | Image-owned initialization and diagnostic helpers |
| `/usr/lib/systemd/system/` | Azurefin-owned initialization and mount integration |
| `/var/lib/azurefin/nix/` | Initialization state and schema/version metadata |
| `/etc/nix/nix.conf` | Regular file, administrator-editable with sudo |
| `~/.config/nix/nix.conf` | Per-user Nix client preferences |
| `~/.config/nixpkgs/config.nix` | Per-user Nixpkgs policy for evaluations that read it |

Do not populate a working store in an image's `/var` and expect later image
updates to synchronize it. OSTree does not apply ordinary image updates to
existing `/var` contents. Store the bootstrap payload under `/usr` instead.

## Configuration contract

1. Seed minimal `/etc/nix/nix.conf` defaults only when the file is absent.
   Never replace it on boot, repair, installer retries, or image upgrades.
2. Keep it a writable regular file, not a symlink into `/usr` or the Nix store.
   Root owns global settings; ordinary users configure their own client files.
3. Keep a reference default file under `/usr/share/azurefin/nix/` so administrators
   can compare new recommendations without applying them automatically.
4. Verify that the pinned installer's configuration actions respect this
   contract. If they do not, adapt the installation plan before integrating it;
   a comment promising preservation is not sufficient.
5. Use the normal Nix precedence rules. Per-user settings do not grant authority
   to override daemon-restricted options. Do not make every user a trusted user.
6. Proposed initial defaults: sandboxed builds, the dedicated build-users group,
   and `nix-command`/`flakes` enabled. Confirm the exact settings in the prototype;
   avoid custom caches, automatic flake-config acceptance, or user-specific paths.
7. Explain that daemon-setting changes require restarting the daemon after active
   builds finish. New clients read client settings on subsequent invocations.

`allowUnfree` is a Nixpkgs option, not a `nix.conf` setting. Do not enable it
globally or modify users' home directories. Document the opt-in example:

```nix
# ~/.config/nixpkgs/config.nix
{
  allowUnfree = true;
}
```

Pure flake evaluation does not automatically consume this file. Document explicit
`config.allowUnfree = true` when importing Nixpkgs in a project, and selective
`allowUnfreePredicate` as an alternative. Users can choose different policies.

## Boot and initialization lifecycle

Proposed ordering: persistent `/var` available -> create state directories ->
mount `/nix` -> initialize if needed -> expose/start the daemon and shell tools.

- Use a single initializer with a lock to prevent concurrent installation.
- Order the mount after its backing directory is available; verify mount identity
  before writing. Never install into the image's unmounted `/nix` directory.
- Explicitly handle separate `/var`, an encrypted backing filesystem, and a full
  filesystem. Nix starts after normal root unlock; it has no pre-unlock role.
- Keep desktop boot usable if initialization fails. Record a clear journal error
  and provide an explicit status/retry operation without destructive cleanup.
- Do not rely on `ConditionFirstBoot=yes`: upgrades to existing installations
  also need initialization. Use durable state plus actual installation checks.
- Distinguish absent installation, Azurefin-managed partial installation,
  healthy installation, and foreign/conflicting installation.
- Write completion metadata atomically only after validating the store, accounts,
  configuration, SELinux setup, mount, and daemon operation.
- First-release decision (2026-11-05): an interrupted installation without a
  reliable receipt retains all partial data and requires guided manual repair.
  Do not automatically resume, replay actions, uninstall, or reset the store.
  Preserve ownership metadata, logs, accounts and administrator configuration
  for diagnosis; a receipt alone is not proof that the runtime is healthy.
- Retain stable build-user IDs and ownership across upgrades and rollbacks. Detect
  account collisions before modifying users or files.
- Provide shell integration for supported shells without modifying each user's
  dotfiles or repeatedly appending PATH entries. Leave Homebrew functional.

The current upstream OSTree planner starts systemd units and emits its own mount
and directory services. It must not be run unchanged inside a Containerfile.
During prototyping, select one owner for each mount/daemon unit and resolve any
installer-generated `/etc` units that would shadow Azurefin's `/usr` units.
Avoid synchronous service-start dependency cycles when invoking the installer
from the initialization service. The exact offline flags and service arrangement
are implementation gates, not assumed working commands.

## Build integration

Follow the existing Homebrew pattern: immutable payload in the image, mutable
installation initialized on the device. Proposed files and changes:

| File or area | Planned change |
| --- | --- |
| `surface/build/15-nix.sh` | Stage and verify pinned artifacts, mount point, defaults, and integration |
| `surface/nix/` | Artifact manifest, helpers, systemd units, shell integration, documentation |
| `Containerfile.romulus` | Explicitly invoke Nix setup in the shared `packages` stage |
| `Containerfile.romulus-local` | Ensure derived releases inherit support; avoid duplicate initialization assets |
| `Containerfile.installer` and other live-image builders | Disable initialization and daemon activation in live sessions only |
| `surface/` tests | Lifecycle, configuration-preservation, and boot integration coverage |
| `README.md` | User-facing availability, configuration, upgrades, troubleshooting, and limitations |

Verify artifact architecture (`aarch64-linux` initially), version, checksum,
provenance, and redistribution requirements during build. Include everything
needed for initialization, including policy resources, without fetching channels
on first boot. Record payload size and installed disk overhead.

Ensure live-image masks do not leak into the installed payload. Firmware-free
and locally provisioned image paths must both retain the same Nix support.
Do not alter Azurefin's firmware provisioning, signing, or OTA channel policies.

## Updates, rollback, and removal

- Image updates can change integration code and bootstrap payloads; they must not
  reinstall Nix, overwrite configuration, or reset profiles on initialized devices.
- A new bundled Nix version affects new installations. Existing runtime upgrades
  use an explicitly documented administrator operation; no automatic runtime
  upgrade or garbage-collection timer is included in the initial scope.
- Document how security fixes reach existing runtimes independently of OS updates.
- Version persistent initialization metadata and keep readers compatible with the
  previous image. Never downgrade a store database during bootc rollback.
- Rollback to an image predating `/nix` support may leave Nix unavailable even
  though data remains in `/var`. Document this recovery boundary and test it.
- Disabling Nix stops activation and retains data. Destructive uninstall must be
  a separate, explicit administrator action; do not delete the store on rollback.
- Existing foreign installations require a documented adoption/migration procedure
  before Azurefin manages them. Initial implementation may report and skip them.

## Implementation phases

1. **Prototype compatibility.** Pin upstream versions, prove offline installation
   on an enforcing aarch64 bootc VM with read-only root and an image-provided
   `/nix`. Resolve installer flags, unit ownership, existing-config handling,
   account allocation, and restart/recovery behavior.
2. **Implement image support.** Add artifacts, mount point, initializer, units,
   defaults, and shell integration. Integrate all installed image variants and
   exclude live-session activation.
3. **Implement lifecycle handling.** Cover interrupted setup, upgrade introduction,
   foreign installations, schema compatibility, diagnostics, and explicit retry.
4. **Validate updates and policy.** Exercise the matrix below, then test on Surface
   hardware through Azurefin's existing deployment path.
5. **Document and release.** Update README, publish configuration and maintenance
   instructions, record tested versions/results, and follow the normal testing
   release process before wider rollout.

## Acceptance checklist

- [x] Offline fresh boot initializes Nix and serves two ordinary users (disposable ARM64 VM; newer-base repeat pending).
- [x] Initialization requires no composefs disablement, transient root, or manual initramfs edit.
- [x] `/nix` is the expected persistent bind mount after reboot.
- [x] Sandbox builds and daemon access work with SELinux enforcing; relevant AVCs are reviewed.
- [x] Network-disabled initialization makes no required downloads or channel updates.
- [ ] Interrupted installation, full disk, and repeated retry preserve recoverable state.
- [ ] Existing healthy and foreign Nix installations are not overwritten.
- [ ] Administrator configuration survives initialization retry, image upgrade, and reboot.
- [x] Two users can select different Nix and Nixpkgs preferences without elevated privileges.
- [x] Unfree policy is opt-in; channel/import and pure-flake examples behave as documented.
- [ ] Nix profiles/packages survive reboot, image upgrade, and supported image rollback.
- [ ] Rollback to a pre-integration image preserves data and has documented recovery.
- [ ] Supported shells find Nix without breaking Homebrew or duplicating PATH entries.
- [ ] Live installer does not initialize Nix; installed payload still does.
- [ ] Initialization failure does not prevent desktop login.
- [ ] ShellCheck, unit validation, relevant lifecycle tests, and `bootc container lint` pass.

## References

- [OSTree persistent `/var` semantics](https://ostreedev.github.io/ostree/var/)
- [OSTree root configuration](https://ostreedev.github.io/ostree/man/ostree-prepare-root.html)
- [NixOS community installer](https://github.com/NixOS/nix-installer)
- [Current OSTree installer planner](https://github.com/NixOS/nix-installer/blob/main/src/planner/ostree.rs)
- [Nix configuration and precedence](https://nix.dev/manual/nix/stable/command-ref/conf-file.html)
- [Nixpkgs unfree package configuration](https://nixos.org/manual/nixpkgs/stable/#sec-allow-unfree)
- Existing Azurefin integration: `surface/build/15-homebrew.sh`,
  `Containerfile.romulus`, `Containerfile.romulus-local`, and `Containerfile.installer`.

Upstream links describe moving versions. Record exact installer/Nix versions and
source revisions during phase 1 before committing implementation assumptions.
