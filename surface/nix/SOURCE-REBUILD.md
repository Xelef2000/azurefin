# Pinned bootstrap sources and rebuilds

This describes the **local prototype**, not a published source release. The
source collection accompanies the unchanged NixOS installer; Azurefin's Python,
shell and systemd integration is separate and lives in this repository.

## What is pinned

The authoritative binary digest and installer revision are in `artifacts.json`.
For installer 2.35.4 the source revision is
`b19d98670014a6e8d3e328d91388db3eae8ccce8`. Its `flake.lock` pins Nix,
Nixpkgs, Crane and the other recipe inputs. `Cargo.lock` pins the Rust crates.
Do not substitute current branches or regenerate either lockfile.

The local collection includes:

- Full installer and Nix project sources, including parent licenses omitted by
  filtered component source trees.
- All 183 locked registry crate sources and their original checksum metadata.
- The 120 direct source/patch roots associated with all 63 embedded runtime
  outputs, plus the pinned flake inputs and their build recipes.
- The identified native musl and Rust sources/patches; the runtime collection
  also includes GCC sources and runtime exception notices.
- Content-addressed notice copies with indexes preserving original paths and
  hashes. Full source archives retain source-header notices as well.
- The complete evaluated derivation graph and payload/source inventory reports.

The collection is intentionally broader than the set of linked libraries. A
license attached to a build tool or test fixture is not automatically the
license of the resulting executable. Keep original notices rather than
flattening everything into the installer's LGPL declaration.

## Verify and inspect

`collect_sources.py` repeats source collection without network access or build
execution once the reviewed inputs have been fetched:

```sh
python3 surface/nix/collect_sources.py \
  --payload payload-inventory.json \
  --derivations installer-derivations.json \
  --flakes installer-flake-archive.json \
  --native installer-native-source-plan.json \
  --vendor /path/to/installer-vendor \
  --output /path/to/new-source-collection
```

The output directory must not exist. The collector checks the ARM64 artifact pin,
all runtime output matches, the native plan against the derivation graph, the
source paths and every vendored file checksum. It archives 139 source/recipe
roots and 183 crates for this pin, normalizes archive timestamps/ownership, and
generates `SHA256SUMS`. The reviewed native plan is still an explicit input, not
an automatic claim to discover all static dependencies. Separate notice indexes
are generated separately:

```sh
python3 surface/nix/inventory_notices.py \
  --source-paths /path/to/new-source-collection/evidence/source-paths.txt \
  --overrides surface/nix/notice-overrides.json \
  --vendor /path/to/installer-vendor \
  --output /path/to/new-notice-collection
```

The overrides are pinned source paths and exact notice filenames. Update and
review them when changing the installer pin; a missing explicit notice fails
collection. Discovery also retains notices from build/test sources, so counts
are not counts of linked libraries. Including plural notice filenames, the run retained 4,428 indexed entries
(about 8.3 MiB including indexes), without extracting archive member paths.

Two independent source-collection runs produced identical source archive hashes:

- `source-trees.tar.zst`: `3880cc78822d921f4defb2d40f5661d39af7359762cc0aff0869309eff6bb524`
- `cargo-vendor.tar.zst`: `a717164b0a8827c1802e74bfc76a964f245c6742c9801b703e78c4028ffb17df`

These are local intermediate archive checksums, not published download promises.

To assemble a combined local collection, repeat `collect_sources.py` with
`--notices /path/to/new-notice-collection` and a new output directory. It verifies
the notice text hashes and the source-root set, and requires runtime coverage
using `notice-parents.json`. All ten Nix outputs retain the full parent project
notices, including components that also contain third-party licenses. The
combined collection includes the generator sources and their Apache-2.0 license.

Run `sha256sum --check SHA256SUMS` at the collection root. Extract into a new
scratch directory, not `/`: some archives preserve `nix/store/...` relative
paths for comparison with the derivation graph. Do not overwrite a working
Nix store with an archive extraction.

The inventory commands are read-only; they do not execute source build scripts:

```sh
python3 surface/nix/inventory_payload.py aarch64-linux /path/to/nix-installer-aarch64-linux > payload-inventory.json
python3 surface/nix/inventory_vendor.py /path/to/installer/Cargo.lock /path/to/installer-vendor > vendor-inventory.json
python3 surface/nix/inventory_sources.py payload-inventory.json installer-derivations.json > runtime-source-inventory.json
```

The source matcher rejects an unknown derivation schema or an unmatched runtime
output. It does not infer licenses or certify binary reproducibility.

## Build using the pinned upstream recipes

Use an existing Nix development machine, preferably native `aarch64-linux`, or
an explicitly configured ARM64 builder. Do not install or replace system Nix
just to perform this review. Nix commands and flakes must be enabled.

```sh
nix derivation show --recursive github:NixOS/nix-installer/b19d98670014a6e8d3e328d91388db3eae8ccce8#packages.aarch64-linux.default > installer-derivations.json
nix build --no-link --print-out-paths github:NixOS/nix-installer/b19d98670014a6e8d3e328d91388db3eae8ccce8#packages.aarch64-linux.default
```

These commands may fetch pinned sources, dependencies and cached build outputs.
They are **not an offline rebuild recipe**. To rebuild rather than substitute
the installer, use Nix's rebuild/check facilities on the resulting derivation
in the disposable build environment. A full from-source closure rebuild also
requires its compiler/toolchain inputs; the collection does not promise an
air-gapped toolchain bootstrap.

The package result contains `bin/nix-installer`. The flake builds the bare Rust
installer, constructs the Nix/certificate runtime archive, then uses
`scripts/pack` to append it. A Cargo-only build is not a replacement for this
packaged artifact. Preserve the installer recipe's NSS certificate override and
Nix's mimalloc override.

Compare a rebuilt artifact against `artifacts.json` and inventory it separately.
The local investigation has established matching runtime output paths and
recipes, **not** a bit-for-bit rebuild of the release executable. If hashes
differ, investigate; do not replace the trusted pin automatically.

## Source-level distinctions checked locally

- `libgit2/COPYING` retains GPL version 2 and its explicit linking exception.
- GCC `COPYING.RUNTIME` retains Runtime Library Exception 3.1 alongside the
  relevant GPL texts; it is not replaced by a generic GPL label.
- ACL `doc/COPYING` distinguishes LGPL library components from GPL components.
  Keyutils `README` likewise distinguishes the LGPL library from GPL tools.
  Both sets of original notices remain in the sources.
- SQLite `LICENSE.md` declares the database implementation public domain but
  separately identifies permissively licensed build helpers. The full file and
  helper notices are retained.
- NSS certificate data has its MPL notice in `certdata.txt`; Boehm GC notices
  occur in README files and source headers. Filename-only scanning is not enough.
- Each filtered Nix component inherits the full project's `COPYING`, in addition
  to notices for embedded third-party code such as wide-character-width tables.
- The installer embeds `src/action/linux/selinux/nix.pp`. Its accompanying
  `nix.te`, `nix.fc` and `build.sh` must remain in the source collection.

### Embedded SELinux policy check

The module rebuilt locally with `checkmodule -M -m -c 5` is byte-identical to
the module unpacked from the pinned `nix.pp`. Repackaging initially differed by
one byte because the checked-in `nix.fc` ends with a newline while the embedded
file-context payload does not. Using the same file contexts without that final
newline reproduces the complete policy package, SHA256
`cdc9ed1b52330491a4b676d261eb3028f1a03d39f4bf52b136ebaa40dd5c83c4`.
This check only compiled/unpacked files in scratch space; it did not load a
policy into the host. The upstream `build.sh` also references an absent
`determinate-nix.fc` for a second, unrelated output, so use its first two commands
when rebuilding this Linux policy rather than expecting the entire script to
finish successfully.

Before publication, make generation repeatable, verify the final archive and
its notice indexes, and publish sources/notices alongside the matching binary
release. Do not describe this interim collection as complete legal clearance.
