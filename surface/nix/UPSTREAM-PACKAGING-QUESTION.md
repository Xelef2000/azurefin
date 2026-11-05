# Local investigation: source/license bundle for the embedded Linux payload

Not submitted upstream. On 2026-11-05 the user chose to keep this investigation
local. Do not open an upstream issue. Publication of a Nix-enabled image remains
blocked until the accompanying source and license material is accounted for;
private local prototype testing can continue.

We are prototyping offline multi-user Nix initialization for an immutable
Fedora-derived image. The intent is to bundle the unchanged official
`nix-installer-aarch64-linux` 2.35.4 release asset, retaining attribution and
providing the appropriate accompanying license notices and sources before
publishing a Nix-enabled image.

The asset SHA256 is
`4f02039533e0912cb5e6f819a2abcac87d78e19b76e377c2ee98e5ec10402341`.
We inspected the trailer layout documented by `scripts/pack` at
`b19d98670014a6e8d3e328d91388db3eae8ccce8`. Its metadata identifies Nix 2.35.4;
the embedded tarball contains the Nix runtime and third-party store outputs.
We did not find files named LICENSE/COPYING in that tarball, or a separate
source/license bundle among the release assets. This may simply mean we are
looking in the wrong place; it is not a claim about upstream compliance.

Local investigation must identify or assemble:

1. The applicable license notices for the static installer and its embedded
   runtime dependencies.
2. The matching source bundle/build recipes, including Rust dependencies and
   the runtime closure, tied to the released binary.

We found the pinned installer source, `Cargo.lock`, `flake.nix` and `flake.lock`.
Inspect those inputs for an existing generator or documented workflow, and
derive a reproducible inventory from the pins where needed. Verify the exact
license expressions against source notices rather than assuming the installer's
license covers the embedded runtime.

This investigation concerns redistribution packaging, not changing installer
behavior or asking upstream to support our boot integration.

## Evidence and remaining work

- Whole-artifact verification and `inventory_payload.py` identify 63 ARM64 store
  outputs; no recognizable license/notice filenames were found inside that
  runtime tarball. The closure registration is retained in the generated report.
- The installer's `Cargo.toml` declares `LGPL-2.1`. Preserve that upstream spelling
  rather than asserting `-or-later` without establishing it from source notices.
- Installer source and build recipes are pinned at
  `b19d98670014a6e8d3e328d91388db3eae8ccce8`; Nix source at
  `21286d605815196c3fff1960550ab08700fc4e6f`; Nixpkgs at
  `cd4ea8d57de16f4810bc5f14207bac45fbf19f67`.
- `runtime-license-candidates.nix` supplies preliminary package metadata, not
  proof of exact binary correspondence. In particular, installer `flake.nix`
  overrides NSS certificate data to 3.131.1, while Nix's
  `packaging/dependencies.nix` overrides mimalloc to 3.5.1. Raw Nixpkgs defaults
  alone therefore do not describe the shipped closure.
- Preserve complete license expressions and exceptions. Examples needing
  source-level review include GCC runtime exceptions, libgit2's linking
  exception, library-versus-command licensing in acl/keyutils, and SQLite's
  public-domain statement (which has no SPDX ID in this Nixpkgs metadata).
- Vendor the installer's exact Cargo.lock dependencies, retaining original
  source notices and checksums; inventory target/build dependencies separately
  from what is actually linked. Include native/static dependencies and the
  embedded SELinux policy's source/build instructions.
- Archive the applicable runtime sources, patches and build definitions and
  generate checksummed notices/source artifacts. Do not treat source URLs or
  Nixpkgs `meta.license` alone as the finished redistribution bundle.

The inventory and source assembly remain local. Nothing in this directory
enables publication of Nix binaries in release workflows.

## Local results (2026-11-05)

`cargo vendor --locked` completed for all 183 registry dependencies.
`inventory_vendor.py` matches package checksums to Cargo.lock and verifies
vendored file checksums, preserving the original license expressions and notice
paths. All crates declare a license. Thirteen have no separately recognized
notice filename; none occurs in `cargo tree --locked --offline --target
aarch64-unknown-linux-musl --edges normal,build` with default features. This is
an over-inclusive source inventory, not a claim that all 183 crates are linked
into the Linux executable.

Evaluating the pinned Nix flake's `packages.aarch64-linux.nix.outPath` produced
`/nix/store/yv1zf3y6all4j99aad30cb8i55dw9zmp-nix-2.35.4`, exactly matching the
embedded runtime root. Use its recursive derivation graph to match individual
runtime outputs and source inputs; retain the certificate override separately.
This establishes a useful recipe/output match, not a bit-for-bit rebuild test.

The recursive graph for the pinned installer's `packages.aarch64-linux.default`
matches **all 63 runtime output paths**, including the certificate bundle.
It also records static-installer build inputs. Export it locally with:

```sh
nix derivation show --recursive github:NixOS/nix-installer/b19d98670014a6e8d3e328d91388db3eae8ccce8#packages.aarch64-linux.default > installer-derivations.json
```

Nix 2.34.8 exports schema 4: derivations are under `derivations`, paths in
`outputs` are store-relative, and some source/build attributes live under
`structuredAttrs` rather than `env`. Preserve both forms when collecting source
inputs. The graph is not itself the corresponding-source archive: those source
inputs and notices still need to be collected and checked.

All 120 unique direct runtime source/patch store roots were collected locally
from the signed Nix cache or were already materialized by evaluation. The local
`runtime-direct-sources.tar.zst` is approximately 404 MiB, SHA256
`0ab9139e848e80829e7cce46de1761ea395dc5a19583e24d0b33716b7f1c674d`.
It is an intermediate archive, not the finished redistribution bundle.

Read-only discovery in the 60 distinct runtime source inputs found 530
separately named notice files. The ten inputs without such filenames were
accounted for as follows:

- Eight are filtered Nix component trees; retain the pinned full Nix source
  archive and its root `COPYING`, plus component-specific source notices.
- NSS `certdata.txt` carries an MPL-2.0 notice in its header; include the matching
  license text as well as that original source file.
- Boehm GC carries its copyright and permission notices in `README.md`,
  `README.QUICK` and source headers, rather than a file named LICENSE.

The pinned static-installer graph also identifies musl 1.2.5 (with patches) and
Rust 1.95.0 sources; these have been fetched locally. Musl provides `COPYRIGHT`;
Rust provides `COPYRIGHT`, `LICENSE-MIT`, `LICENSE-APACHE`, and `LICENSES/`.
The installer source includes its compiled SELinux policy together with
`nix.te`, `nix.fc` and `build.sh`. Preserve these sources and their provenance.

Next packaging work: assemble the retained notices (including nonstandard
filenames), full project sources, vendored crates, native sources, patches and
recipes into a checksummed distribution bundle; validate completeness against
both runtime and static-installer inputs. No upstream response is needed for
that work.
