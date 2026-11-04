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

1. Prove offline installation and policy loading on the enforcing ARM64 VM.
2. Prove sandbox builds and daemon access for two ordinary users; review AVCs,
   including labels through both `/nix` and `/var/lib/nix`.
3. Add the image-owned mount/daemon units and locked initializer with durable
   ownership metadata, schema validation, explicit status/retry and interruption
   handling. Completion must follow successful daemon checks, not just a receipt.
4. Package licenses/source, shell integration and all offline resources under
   `/usr`; integrate the shared packages stage and live-only exclusions.
5. Test upgrades, rollback, existing configuration, foreign installations,
   separate/encrypted `/var`, full disk and desktop availability on failure.
6. Only then enable image integration, update user-facing availability docs,
   build a signed candidate and request the Surface reboot test.

The default reference enables sandboxing with no fallback, trusts only root,
and does not enable unfree software or custom caches. Existing administrator
configuration is not silently tightened or rewritten.
