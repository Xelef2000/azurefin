#!/usr/bin/python3
"""Anaconda %post: do not remount composefs with backing-filesystem options."""

import configparser
import pathlib
import re
import shutil


def corrected_fstab(text, boot_options, canonical_home):
    lines = text.splitlines(keepends=True)
    entries = [(i, line.split()) for i, line in enumerate(lines)
               if line.strip() and not line.lstrip().startswith("#")]
    if any(len(fields) < 4 for _, fields in entries):
        raise ValueError("Malformed fstab; refusing to edit")
    roots = [(i, fields) for i, fields in entries if fields[1] == "/"]
    if len(roots) > 1:
        raise ValueError("Multiple root entries; refusing to edit")
    if roots:
        index, fields = roots[0]
        required = {"root=" + fields[0]}
        subvols = {v for v in fields[3].split(",")
                   if v.startswith(("subvol=", "subvolid="))}
        for options in boot_options:
            flags = {flag for arg in options if arg.startswith("rootflags=")
                     for flag in arg.removeprefix("rootflags=").split(",")}
            if required.issubset(options) and subvols.issubset(flags):
                break
        else:
            raise ValueError("No boot entry selects the fstab root and subvolume")
        lines[index] = ("# Composefs owns /; root= and rootflags= select its backing filesystem.\n"
                        "# " + lines[index])
    homes = [(i, fields) for i, fields in entries if fields[1] in ("/home", "/var/home")]
    var = [i for i, fields in entries if fields[1] == "/var"]
    if canonical_home and homes:
        if len(homes) != 1 or len(var) > 1:
            raise ValueError("Ambiguous home/var entries; refusing to edit")
        index, _ = homes[0]
        home = re.sub(r"^(\S+\s+)/home(?=\s)", r"\1/var/home", lines[index])
        if var and index < var[0]:
            lines[index] = ""
            lines[var[0]] = lines[var[0]].rstrip("\n") + "\n" + home
        else:
            lines[index] = home
    return "".join(lines)


def fix(root):
    config = configparser.ConfigParser()
    config.read([root / "usr/lib/ostree/prepare-root.conf",
                 root / "etc/ostree/prepare-root.conf"])
    if config.get("composefs", "enabled", fallback="no") not in ("yes", "true", "1", "signed"):
        raise ValueError("Composefs is not explicitly enabled; refusing to edit")
    boot_options = []
    for entry in (root / "boot/loader/entries").glob("*.conf"):
        for line in entry.read_text().splitlines():
            if line.startswith("options "):
                boot_options.append(line.split()[1:])
    home = root / "home"
    canonical_home = home.is_symlink() and str(home.readlink()) in ("var/home", "/var/home")
    path = root / "etc/fstab"
    original = path.read_text()
    updated = corrected_fstab(original, boot_options, canonical_home)
    if updated == original:
        print("Composefs fstab already correct")
        return
    backup = path.with_name("fstab.before-azurefin-composefs")
    if backup.exists():
        raise ValueError("Backup already exists; refusing to overwrite")
    shutil.copy2(path, backup)
    # Keep the existing inode, permissions and SELinux label during %post.
    path.write_text(updated)
    print("Corrected composefs fstab; original saved as", backup)


if __name__ == "__main__":
    fix(pathlib.Path("/"))
