#!/usr/bin/env python3
"""Inventory cargo vendor sources against Cargo.lock without running build scripts.

Includes all locked targets/build dependencies, not just ARM64 linked crates.
Retain whole vendor sources: license expressions alone are not license notices.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tomllib


def inventory(lock_path, vendor):
    lock = tomllib.loads(lock_path.read_text())
    expected = {}
    for package in lock["package"]:
        if "source" not in package:
            continue  # Workspace sources belong in the installer source archive.
        if package["source"] != "registry+https://github.com/rust-lang/crates.io-index":
            raise ValueError("Non-crates.io dependency requires explicit source handling")
        expected[(package["name"], package["version"])] = package["checksum"]
    records = []
    seen = set()
    for manifest in sorted(vendor.glob("*/Cargo.toml")):
        package = tomllib.loads(manifest.read_text())["package"]
        key = (package["name"], package["version"])
        checksum = json.loads(manifest.with_name(".cargo-checksum.json").read_text())
        if key not in expected or key in seen or checksum["package"] != expected[key]:
            raise ValueError(f"Unexpected or mismatched vendored package: {key}")
        seen.add(key)
        notices = []
        for name, digest in checksum["files"].items():
            relative = Path(name)
            path = manifest.parent / relative
            if relative.is_absolute() or ".." in relative.parts or path.is_symlink():
                raise ValueError("Unsafe vendor path")
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError(f"Modified vendor file: {path}")
            if re.match(r"(?i)^(licen[cs]es?|copying|copyrights?|notices?)([._-]|$)", path.name):
                notices.append({"path": name, "sha256": digest})
        records.append({
            "name": key[0], "version": key[1], "crate_sha256": expected[key],
            "license_expression": package.get("license"),
            "license_file": package.get("license-file"),
            "notice_files": sorted(notices, key=lambda item: item["path"]),
        })
    if seen != set(expected):
        raise ValueError(f"Missing vendored crates: {sorted(set(expected) - seen)}")
    return {"schema": 1, "complete_license_inventory": False,
            "scope": "All Cargo.lock registry dependencies, including other targets and build dependencies",
            "lock_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
            "crates": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lock", type=Path)
    parser.add_argument("vendor", type=Path)
    args = parser.parse_args()
    print(json.dumps(inventory(args.lock, args.vendor), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
