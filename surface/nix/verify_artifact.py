#!/usr/bin/env python3
"""Verify a downloaded installer, including embedded payload, before execution."""
import argparse
import hashlib
import json
import struct
from pathlib import Path


def verify(path, artifact):
    if path.stat().st_size != artifact["bytes"]:
        raise ValueError("Installer size does not match pin")
    with path.open("rb") as stream:
        header = stream.read(20)
        stream.seek(0)
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != artifact["sha256"]:
        raise ValueError("Installer SHA256 does not match pin")
    if header[:6] != b"\x7fELF\x02\x01":
        raise ValueError("Expected a little-endian ELF64 executable")
    if struct.unpack_from("<H", header, 18)[0] != artifact["elf_machine"]:
        raise ValueError("Installer architecture does not match pin")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("architecture", choices=("aarch64-linux", "x86_64-linux"))
    parser.add_argument("installer", type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path(__file__).with_name("artifacts.json").read_text())
    verify(args.installer, manifest["artifacts"][args.architecture])
    print(f"Verified installer {manifest['installer_version']} for {args.architecture}")


if __name__ == "__main__":
    main()
