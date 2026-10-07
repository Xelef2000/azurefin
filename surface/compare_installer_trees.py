#!/usr/bin/env python3
"""Compare two read-only installer trees; ignore physical directory sizes/inodes."""
import hashlib
import os
from pathlib import Path
import stat
import sys


def digest(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").digest()


def compare(source, result):
    stack = [Path(".")]
    files = entries = 0
    # Preserve regular-file hardlink groups, independently of inode numbers.
    source_links, result_links = {}, {}
    while stack:
        relative = stack.pop()
        a, b = source / relative, result / relative
        sa, sb = a.lstat(), b.lstat()
        metadata = lambda s: (s.st_mode, s.st_uid, s.st_gid, s.st_mtime_ns)
        if metadata(sa) != metadata(sb):
            raise ValueError(f"Metadata mismatch: {relative}")
        xa = {n: os.getxattr(a, n, follow_symlinks=False)
              for n in os.listxattr(a, follow_symlinks=False)}
        xb = {n: os.getxattr(b, n, follow_symlinks=False)
              for n in os.listxattr(b, follow_symlinks=False)}
        if xa != xb:
            raise ValueError(f"Extended attribute mismatch: {relative}")
        entries += 1
        if stat.S_ISDIR(sa.st_mode):
            names_a, names_b = set(os.listdir(a)), set(os.listdir(b))
            if names_a != names_b:
                raise ValueError(f"Directory entries mismatch: {relative}")
            stack.extend(relative / name for name in sorted(names_a, reverse=True))
        elif stat.S_ISLNK(sa.st_mode):
            if os.readlink(a) != os.readlink(b):
                raise ValueError(f"Symlink target mismatch: {relative}")
        elif stat.S_ISREG(sa.st_mode):
            first_a = source_links.setdefault((sa.st_dev, sa.st_ino), relative)
            first_b = result_links.setdefault((sb.st_dev, sb.st_ino), relative)
            if first_a != first_b:
                raise ValueError(f"Regular-file hardlink mismatch: {relative}")
            if sa.st_size != sb.st_size:
                raise ValueError(f"File size mismatch: {relative}")
            if first_a == relative:
                if digest(a) != digest(b):
                    raise ValueError(f"File contents mismatch: {relative}")
                files += 1
                if files % 10000 == 0:
                    print(f"Verified {files} unique regular files", flush=True)
        elif sa.st_rdev != sb.st_rdev:
            raise ValueError(f"Device number mismatch: {relative}")
    print(f"TREE_CONTENTS_METADATA_VERIFIED: {entries} entries, {files} unique regular files", flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: compare_installer_trees.py SOURCE_DIRECTORY RESULT_DIRECTORY")
    try:
        compare(Path(sys.argv[1]), Path(sys.argv[2]))
    except (OSError, ValueError) as error:
        sys.exit(str(error))
