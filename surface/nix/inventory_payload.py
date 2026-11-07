#!/usr/bin/env python3
"""Inventory a pinned Linux installer without executing it or extracting files.

Requires zstd. This is evidence for source/license packaging, not a complete
SBOM: statically linked installer dependencies require a separate inventory.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import tarfile
import tempfile

from verify_artifact import verify


def split_payload(data):
    if len(data) < 20 or data[-8:] != b"NIXINST1":
        raise ValueError("Missing Linux payload trailer")
    meta_len, payload_len = struct.unpack("<IQ", data[-20:-8])
    meta_start = len(data) - 20 - meta_len
    payload_start = meta_start - payload_len
    if not meta_len or not payload_len or payload_start < 20:
        raise ValueError("Invalid payload lengths")
    metadata = json.loads(data[meta_start:-20])
    if not isinstance(metadata, dict) or not all(
        isinstance(metadata.get(key), str)
        for key in ("nix_store_path", "cacert_store_path", "nix_version")
    ):
        raise ValueError("Invalid payload metadata")
    return data[payload_start:meta_start], metadata


def inventory(stream):
    outputs, notices = set(), []
    registration = None
    with tarfile.open(fileobj=stream, mode="r|") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Unexpected archive path")
            parts = path.parts
            if len(parts) >= 3 and parts[1] == "store":
                if not re.fullmatch(r"[0-9a-z]{32}-.+", parts[2]):
                    raise ValueError("Unexpected store output name")
                outputs.add("/nix/store/" + parts[2])
            if re.match(r"(?i)^(licen[cs]es?|copying|copyrights?|notices?)([._-]|$)", path.name):
                notices.append(member.name)
            if path.name == ".reginfo":
                if registration is not None or not member.isfile() or member.size > 4 * 1024 * 1024:
                    raise ValueError("Unexpected closure registration")
                registration = archive.extractfile(member).read().decode("utf-8")
    if not outputs or registration is None:
        raise ValueError("Missing runtime closure or registration")
    return {
        "store_outputs": sorted(outputs),
        "notice_paths": sorted(notices),
        "registration": registration,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("architecture", choices=("aarch64-linux", "x86_64-linux"))
    parser.add_argument("installer", type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path(__file__).with_name("artifacts.json").read_text())
    pin = manifest["artifacts"][args.architecture]
    verify(args.installer, pin)
    payload, metadata = split_payload(args.installer.read_bytes())
    with tempfile.TemporaryFile() as compressed, tempfile.TemporaryFile() as expanded:
        compressed.write(payload)
        compressed.seek(0)
        subprocess.run(["zstd", "-d", "-c"], stdin=compressed, stdout=expanded, check=True)
        expanded.seek(0)
        result = inventory(expanded)
    expected = {metadata["nix_store_path"], metadata["cacert_store_path"]}
    if not expected.issubset(result["store_outputs"]):
        raise ValueError("Metadata roots missing from closure")
    result.update(
        schema=1, architecture=args.architecture,
        installer_sha256=pin["sha256"], source_revision=manifest["source_revision"],
        payload_sha256=hashlib.sha256(payload).hexdigest(), metadata=metadata,
        complete_license_inventory=False,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
