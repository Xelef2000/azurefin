#!/usr/bin/python3
"""Append an opt-in entry, preserving every byte of the old GRUB configuration."""
import re
from pathlib import Path
import sys


def append_entry(text):
    if "--id azurefin-provision" in text:
        raise ValueError("Provisioning entry already exists")
    entries = list(re.finditer(r"(?m)^menuentry ([^\n]*)\{\n(.*?)^\}", text, re.S))
    candidates = [m for m in entries if "--id romulus-preload-display" in m[1]]
    if not candidates:
        candidates = [m for m in entries if "Install Fedora" in m[1]]
    if not candidates:
        raise ValueError("No recognized working boot entry")
    body = candidates[0][2]
    if body.count("inst.ks=") != 1 or "inst.stage2=hd:LABEL=AZUREDATA" not in body:
        raise ValueError("Unexpected existing installer source")
    body = re.sub(r"inst.ks=\S+", "inst.ks=hd:LABEL=AZUREFIN_WORK:/installer-provision.ks", body)
    if "rd.break" in body or "inst.rescue" in body:
        raise ValueError("Refusing a paused/rescue boot entry")
    return text + "\nmenuentry 'Azurefin: prepare firmware then install (test)' --id azurefin-provision {\n" + body + "}\n"


if __name__ == "__main__":
    source, destination = map(Path, sys.argv[1:])
    with destination.open("x") as stream:
        stream.write(append_entry(source.read_text()))
