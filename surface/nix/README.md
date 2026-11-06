# Nix integration prototype

This is phase 1 of the agreed Nix integration plan. It is **not enabled in
Azurefin images** and must not be run on an ordinary workstation or Surface.
No production Containerfile, firmware policy, signing rule or update channel
is changed here. See the [integration plan](../NIX-INTEGRATION-PLAN.md).

## Pinned artifacts and code origins

The [NixOS community installer 2.35.4](https://github.com/NixOS/nix-installer/releases/tag/2.35.4)
at source commit `b19d98670014a6e8d3e328d91388db3eae8ccce8` supplies the installer,
embedded Nix bootstrap closure and compiled SELinux policy. Its published ARM64
binary is 32,698,235 bytes (31.2 MiB). `artifacts.json` pins the whole binary,
including its payload, by SHA256 and architecture. The x86-64 artifact is for
development checks, not a new supported Azurefin target.

Download the named release asset, then run `verify_artifact.py` before executing
it. No latest-version URL or runtime network fetch is used. Redistribution must
retain the upstream LGPL license and provide corresponding source, including
the payload's dependency licenses. The shipping payload stage still needs this
license/source packaging; this prototype does not distribute the binaries.

Upstream's OSTree planner creates `/etc` mount/service overrides and can run
`chattr`. We instead use its supported editable-plan interface with the Linux
planner, `--init none --no-start-daemon --no-modify-profile --skip-nix-conf`.
Channel setup is disabled by default and checked explicitly in the plan.

`adapt_plan.py` rejects version/settings/action-list drift, requires a mounted
`/nix`, leaves configuration/profile modifications disabled, relocates the
embedded SELinux policy from read-only `/usr` to `/etc/nix-installer`, and omits
the actions for Azurefin-owned mount points and systemd configuration. Provisioning,
accounts, default profile, policy and scratch cleanup remain upstream actions.
This is a version-specific adapter, not a generic untrusted-plan validator.

## Disposable guest test

Use a full-system enforcing ARM64 bootc VM, not ARM64 user-mode emulation.
The image must provide a real empty `/nix`; the guest must bind persistent
`/var/lib/nix` there with root ownership and mode 0755. Do not make the root
writable or transient to satisfy this prerequisite.

Copy this directory and the verified ARM64 installer into that disposable VM:

```sh
sudo env AZUREFIN_NIX_DISPOSABLE_GUEST=yes bash prototype.sh /path/to/nix-installer-aarch64-linux
```

The script is deliberately fresh-install-only and refuses account/store
collisions. It preserves existing regular `nix.conf`, seeds only an absent file,
and performs the installation inside a network namespace without networking.
It does not configure a daemon or declare initialization complete. Do not run
the installer uninstall command against an Azurefin-managed production store.

Run local adapter checks:

```sh
python3 -m unittest discover -s surface/nix -p 'test_*.py' -v
python3 surface/nix/verify_artifact.py aarch64-linux /path/to/nix-installer-aarch64-linux
shellcheck surface/nix/prototype.sh
```

### Local full-system VM image

`Containerfile.prototype` adds a diagnostic service to an existing ARM64 bootc
image. It is not referenced by release workflows. Supply a verified installer
as a named build context:

```sh
podman build --pull=never --platform linux/arm64 \
  --build-context nix-payload=/path/to/verified-artifacts \
  --build-arg BASE_IMAGE=localhost/azurefin:test-base \
  -f surface/nix/Containerfile.prototype -t localhost/azurefin:nix-prototype .
```

Deploy that image only to a new disposable VM disk. Do not attach host physical
disks. Boot with SELinux enforcing and no network device. The diagnostic checks
read-only root and mount identity before invoking the installer. Serial/journal
marker `AZUREFIN_NIX_VM_BOOTSTRAP_COMPLETE` means only bootstrap succeeded, not
that multi-user operation, sandboxing or upgrade safety has passed. These VM
units intentionally have no production recovery or daemon integration.

The prototype installs `/etc/profile.d/azurefin-nix.sh` for Fedora's Bash and
POSIX login-shell startup. New shells automatically append user Nix profile
locations and the system Nix profile to PATH, preserving system/Homebrew
precedence. Re-sourcing does not duplicate entries. Paths are included even
before they exist so shells started during asynchronous initialization can find
Nix when it becomes ready, without a logout. No directories or user dotfiles
are created by this hook. This is currently prototype-only; Fish and other
shell-specific startup integration remain to be validated before release.

For virtio test-disk safety checks, use a short serial identifier and compare it
exactly before installation: the original long identifier was truncated in the
guest, correctly causing our first deployment attempt to stop without writing.

### Full-system validation status — 2026-11-05

- Prototype ARM64 image builds; `bootc container lint` reports 14 passes and
  one skipped check.
- Prototype systemd unit verification passes.
- Full-system offline bootstrap completed on ARM64, with SELinux enforcing,
  read-only composefs root and `/nix` backed by persistent `/var/lib/nix`.
  Nix 2.35.4 executed successfully by its absolute path.
- Upstream shell self-tests reported missing PATH integration. The new profile
  fragment addresses this; login-shell PATH passed for both ordinary test users.
- The bootstrap VM remained at its login prompt until the harness timeout.
  The bootstrap completion marker preceded that timeout; it is not a daemon
  or sandbox validation result.
- `vm-multiuser.sh` and its diagnostic units test the next stage on that
  disposable disk: two new ordinary users, login-shell PATH, explicit daemon
  connections and offline builds using the bundled BusyBox. Builds must run
  under a build-user UID and cannot see a host-only marker. The test powers off
  after success or a trapped command failure. These units are not enabled by
  the prototype Containerfile or release workflows; the script is staged under
  `/var/tmp` in the stopped test VM. Both users completed offline builds with
  non-root sandbox UID 1000, the host-only marker was hidden, SELinux remained
  enforcing, and no AVC denials appeared in the successful run's serial log.
- First multi-user run confirmed login-shell PATH and an ordinary user's daemon
  connection. The build failed because the bundled minimal BusyBox has no `id`
  applet. The revised test reads `/proc/self/status` using shell builtins and
  checks a non-root effective UID (a user namespace may map the host build UID).
  It also prints the successful build output. The revised test passed.
- The pinned upstream `nix.fc` labels executable/library subtrees but does not
  label the store root, and `nix.te` does not define a confined daemon domain.
  Thus `default_t` on the store directory and `unconfined_service_t` on the daemon
  alone do not demonstrate a failed policy install. The retry checks the resolved
  daemon executable against policy and lists the loaded module. This upstream
  compatibility policy must not be described as dedicated daemon confinement.
- The module-list check initially assumed a trailing version field. This
  libsemanage prints names alone; accepting end-of-line fixed the diagnostic.
  The loaded module and executable label both verified on the successful run.
- `vm-persistence.sh` is a separate two-boot test using the same disposable
  service entry point. It creates user profiles, records checksums of build
  outputs, administrator-customized configuration, receipt and accounts, then
  verifies them after a new boot and exercises both users through the daemon.
  It also checks that the fresh-only prototype refuses an existing store
  without changing those checksums. Both boots passed, including daemon access
  with `Trusted: 0` for ordinary users and unchanged account/configuration/receipt
  checksums after the refusal test. This does **not**
  validate image upgrades, rollback or interrupted-install recovery.
- `vm-relabel.sh` proved the backing path needs a file-context equivalence:
  `/var/lib/nix` maps to `/nix`. After applying it and relabeling through the
  backing path, both executable-path label checks and both forced sandbox
  rebuilds passed. One pre-existing boot-time systemd/netlink AVC appeared
  before the test; no Nix build AVC was reported.

### Guarded initializer work

`lifecycle.py` and `initialize.py` are still disposable-VM prototypes, not
production services. Initialization and final validation are separate so the
initializer never synchronously starts a daemon ordered after itself. Versioned
ownership metadata records pinned installer/plan hashes and progress, uses a
non-blocking lock and atomic, fsynced updates, and never treats a receipt alone
as proof of runtime health. Defaults are published atomically only when no
administrator configuration exists.

An unowned store/account collision is classified as foreign. A hard-interrupted
installation is retained as needing reconciliation; it is not erased or blindly
replayed. Unknown schema versions and changed action arguments are rejected.
Completed runtimes are validated rather than reinstalled when the bundled
installer changes. Unit tests cover lock exclusion, an abruptly exiting process,
full-disk checkpoint/config writes, symlink refusal and configuration retention.
These are fault-injection tests, not yet full power-loss or image-upgrade tests.

`vm-initializer.sh` resets only an explicitly marked copy-on-write test overlay,
preserving the original store under another directory inside that overlay. It
tests initialization, administrator configuration preservation and repeated
validation; those checks passed on the second overlay. The first fixture reset
stopped its own required mount unit and was discarded; the corrected fixture
keeps the mount unit active while replacing only the overlay's backing store.
It must never run on a user installation.

`vm-fault.sh` runs in separate marked overlays with an 8 MiB temporary store or
a killed initializer process group. It checks that retries retain partial state
and configuration instead of replaying installation. Both VM runs passed on
2026-11-05 (`AZUREFIN_NIX_FAULT_COMPLETE mode=full` and `mode=killed`).
These are isolated fault tests, not a claim of power-loss recovery support.

### First-release interrupted-installation policy

An uncertain partial installation requires guided manual repair. Automatic
retry must preserve the store, build accounts, configuration, receipt (if any),
and Azurefin ownership metadata. It must not replay installer actions, uninstall
Nix, or delete partial data. This policy was selected on 2026-11-05.

When `needs-reconciliation` is reported:

1. Stop retrying installation; do not run the upstream uninstaller or remove
   `/nix`, `/var/lib/nix`, or `/var/lib/azurefin/nix`.
2. Preserve the installation logs and back up the partial store and ownership
   metadata before making any repair changes. Keep `/etc/nix` and the relevant
   build-account information with that backup; review logs before sharing them.
3. Ask for guided repair with the reported state, image version, installer/plan
   hashes and failure log. Repair must inspect the actual store, accounts and
   receipt against the pinned plan before deciding which steps are safe.

Freeing disk space or rebooting does not by itself make replay safe. A generic
automatic repair/reset command is deliberately not part of the first release.

## Results — 2026-11-04

- Both upstream release asset hashes and ELF architectures verified.
- ARM64 installer runs under local emulation and generates the expected plan.
- Twelve adapter/artifact tests pass, including refusal of configuration/profile changes,
  unmounted stores, unknown versions/actions and unsafe scratch cleanup.
- Network-disabled ARM64 container reached store provisioning, account creation
  and default-profile setup. It then failed loading seccomp BPF under QEMU
  user-mode emulation. This is **not** an offline-installation or sandbox pass.
- An earlier container mount defaulted to world-writable mode. Nix correctly
  refused it; the prototype now explicitly checks mode 0755.
- Upstream receipts are saved on handled cancellation/error and final success,
  not after every action. SIGKILL/power-loss recovery must distinguish a known
  partial installation with no usable receipt; blindly rerunning is unsafe.

## Remaining implementation gates

### Asynchronous systemd prototype — 2026-11-05

`systemd/` contains the proposed directory, mount, initializer, daemon and
validator units. Only a timer is enabled at boot; it schedules validation after
30 seconds, pulling in the ordered dependencies without making the desktop
target depend on Nix. Each unit rejects the live-image kernel command line.
The initializer retains its disposable-guest guard; these units are not enabled
in production. Directory preparation refuses unexpected existing permissions,
ownership and symlinks without silently changing them.

The first systemd run initialized and validated the runtime successfully while
the login target became available. Its subsequent package assertion had a test
fixture error (`--rebuild` before creating the output); the corrected fixture
builds first, then rebuilds. The corrected run and a subsequent reboot passed;
both users built/rebuilt sandboxed outputs and remained untrusted daemon clients.
Offline checksums of the receipt, passwd and group files matched the initial
initialized disk after both boots.

The separate interrupted-installation boot test passed: login/user-session
targets became active, initialization refused with manual-repair guidance,
the daemon stayed inactive, and state/configuration/account checksums matched.
This proves console login-target availability, not yet graphical login on the
Surface.

`Containerfile.systemd-prototype` builds a local-only image with the proposed
files under immutable `/usr`, explicit disposable-test environment overrides,
and a first-boot diagnostic. Its `bootc container lint` passed 14 checks with one
skip. Fresh-image deployment and first boot passed offline on the cached base:
the image-owned initializer completed under enforcing SELinux and read-only
composefs, then both ordinary users built sandboxed outputs. A subsequent
foreign-store overlay test removed only Azurefin's ownership metadata from the
test view: initialization refused, login targets remained available, the daemon
stayed inactive, and configuration/account/store checksums remained unchanged.
The original disk and ownership metadata were retained. Directory preparation
also refuses to hide nonempty foreign `/nix` contents behind its bind mount.

`vm-encrypted-store.sh` passed its two-boot test on a disposable overlay with a
separate 2 GiB virtual LUKS2 volume. The existing store was copied to it, then
mounted by the normal crypttab/fstab units on the next boot. Nix started after
the backing mount; both users could access the daemon and build offline.
Administrator configuration, account files, ownership state and receipt hashes
were unchanged. The fixture's automatic test key is confined to that disposable
guest; it is not a proposed key-storage policy for real installations.

`vm-live-guard.sh` passed on an installed disposable overlay booted with the live
kernel flags. Every Nix unit refused activation through its real systemd
condition, even after an explicit start request; `/nix` stayed unmounted and
store/configuration/account hashes were unchanged. This validates the unit
guard, not yet a newly built Nix-enabled live ISO.

Validation against the newer signature-verified `v0.0.29-alpha-base` is in
progress. The prototype built on that base and passed the same container lint
checks. Do not publish this diagnostic image or use it on a user device.

`vm-preferences.sh` evaluates the pinned Nixpkgs revision
`cd4ea8d57de16f4810bc5f14207bac45fbf19f67` in a separate overlay. It checks
independent user configuration, unfree opt-in and the pure-flake boundary without
downloading or building unfree software. The corrected run passed with
`AZUREFIN_NIX_PREFERENCES_COMPLETE`: independent user settings, untrusted daemon
access, default unfree denial, explicit per-user opt-in, and pure-flake denial
were verified. The first fixture attempt needed correction because
`nix store info` prints its status to stderr.
The source tree is test input only, not part of the bootstrap payload.

### Local source/license inventory

`inventory_payload.py` verifies the complete installer against `artifacts.json`,
reads the upstream Linux trailer, and inventories the embedded tar without
executing the installer or extracting archive paths:

```sh
python3 surface/nix/inventory_payload.py aarch64-linux /path/to/nix-installer-aarch64-linux > payload-inventory.json
```

The pinned ARM64 payload has 63 store outputs. The report includes its closure
registration, roots, compressed-payload hash and any recognizable notice paths.
It explicitly does **not** claim complete license coverage: statically linked
installer dependencies, build inputs, patches and source notices need review
as well. `runtime-license-candidates.nix` evaluates preliminary metadata from
the pinned Nixpkgs source without building packages. Version overrides and
output-specific licensing must be reconciled before using that metadata for
distribution. See [local packaging investigation](UPSTREAM-PACKAGING-QUESTION.md).

`inventory_vendor.py Cargo.lock /path/to/vendor` verifies a `cargo vendor --locked`
tree against the lockfile and its file checksums, reporting original license
expressions and notice paths. The local pinned run covered 183 crates; source
and vendor archives remain local, outside the Git repository. All 63 embedded
runtime output paths were matched to the pinned installer's derivation graph.
The combined source/notice collection described below is now available locally;
publication and production packaging remain outstanding.

`inventory_sources.py` turns a verified payload inventory and the pinned
schema-4 recursive derivation graph into a reproducible direct-source manifest:

```sh
python3 surface/nix/inventory_sources.py payload-inventory.json installer-derivations.json > runtime-source-inventory.json
```

It fails if any payload output cannot be matched and retains multiple providers,
structured attributes, source/patch roots, and hashes of both input reports.
The pinned run matches 63 outputs to 64 provider records and 120 direct source
roots. This does not replace the full recipes, parent project sources, native
installer dependencies or license review.

The local `collect_sources.py` and `inventory_notices.py` tools now reproduce
source and notice collection, with explicit pinned exceptions in
`notice-overrides.json`. See [source/rebuild instructions](SOURCE-REBUILD.md).
The source archives matched across two runs. A combined local collection now
includes 4,428 notice entries, checked text hashes, parent-project mappings for
all ten Nix outputs, and notice coverage for all 63 runtime outputs. It includes
the collector sources and their license. The reviewed snapshot is published as
[Nix sources 2.35.4 r1](https://github.com/Xelef2000/azurefin/releases/tag/nix-sources-2.35.4-r1),
a source-only prerelease. GitHub asset sizes and SHA256 digests matched the local
files. No installer executable or OS image was published; build integration of
the paired artifacts remains.

On 2026-11-06 the outer local archive passed `zstd -t` and its collected files
passed `sha256sum --check`. Source-only release tags are now excluded from the
OS image and downstream ISO workflows. This does not itself publish artifacts
or authorize enabling Nix in production images.

The current-base repeat on signed `v0.0.29-alpha-base` subsequently passed
offline initialization and both ordinary-user sandbox tests. The upgrade
test staged its image but its next boot selected the old deployment: the harness
incorrectly assumed `ostree-1.conf` always identifies the default. The new entry
was `ostree-2.conf` with version 2 and deployment index 0. The corrected harness
selects index zero and rejects ambiguous entries. Its retry passed both the
generation-two upgrade and supported rollback, including both users' daemon
access/offline builds, profile targets, and unchanged administrator configuration,
accounts, receipt and ownership state. Pre-integration recovery is still pending.

The live-session unit guard also passed in a disposable installed-image overlay
booted with `rd.live.image`: explicit starts were skipped, `/nix` remained
unmounted, and persistent store/configuration/account/state checksums remained
unchanged. This is a unit-condition test, not a newly composed live-ISO test.

### Before production integration

1. Offline installation, two-user sandbox builds, reboot persistence and
   backing-path relabel checks passed on the enforcing ARM64 VM. Validate the
   image-owned integration against the current image base; fresh installation
   has passed on the earlier cached base.
2. Validate remaining shell/profile behavior and administrator configuration
   preservation across retries and image updates.
3. Finish validating the proposed image-owned units and initializer together,
   including status/retry and interruption handling. Completion must follow
   successful daemon checks, not just a receipt.
4. Package licenses/source, shell integration and all offline resources under
   `/usr`; integrate the shared packages stage and live-only exclusions.
5. Test upgrades, rollback, existing configuration, foreign installations,
   separate/encrypted `/var`, full disk and desktop availability on failure.
6. Only then enable image integration, update user-facing availability docs,
   build a signed candidate and request the Surface reboot test.

The default reference enables sandboxing with no fallback, trusts only root,
and does not enable unfree software or custom caches. Existing administrator
configuration is not silently tightened or rewritten.
