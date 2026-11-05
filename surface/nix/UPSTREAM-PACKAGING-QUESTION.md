# Draft: source/license bundle for redistribution of the embedded Linux payload

Not submitted upstream; external-repository permission is pending.

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

Is there an existing supported process or artifact for downstream distributors
to obtain:

1. The applicable license notices for the static installer and its embedded
   runtime dependencies?
2. The matching source bundle/build recipes, including Rust dependencies and
   the runtime closure, tied to the released binary?

We found the pinned installer source, `Cargo.lock`, `flake.nix` and `flake.lock`.
Is there an existing generator or documented workflow that derives the above
from those pins, rather than each downstream maintaining a separate inventory?

This question is about redistribution packaging, not changing installer behavior
or asking upstream to support our boot integration.
