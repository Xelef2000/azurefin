#!/usr/bin/env python3
"""Guarded initializer for image-owned Nix integration.

initialize provisions without starting systemd units. finalize is a separate
step after daemon startup, avoiding an initializer/daemon ordering cycle.
Partial installations are retained and reported, never erased or blindly rerun.
"""
import argparse
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys

from adapt_plan import adapt
from lifecycle import classify, digest, locked, read_state, receipt_matches, seed_config_file, write_state
from verify_artifact import verify

RESOURCES = Path(__file__).resolve().parent
STATE = Path("/var/lib/azurefin/nix")
INSTALLER = Path("/usr/libexec/azurefin-nix-installer")


def run(*args):
    result = subprocess.run(args, text=True, capture_output=True)
    if result.returncode:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        result.check_returncode()
    return result.stdout.strip()


def image_owned():
    marker = RESOURCES / 'installed-image.json'
    if not marker.exists():
        return False
    info = marker.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise RuntimeError('Unsafe image integration marker')
    return json.loads(marker.read_text()) == {'schema': 1}


def preflight():
    if os.geteuid() != 0:
        raise RuntimeError('Nix initialization requires root')
    if os.environ.get("AZUREFIN_NIX_DISPOSABLE_GUEST") != "yes" and not image_owned():
        raise RuntimeError("Requires image-owned integration or an explicit disposable guest")
    if run("getenforce") != "Enforcing":
        raise RuntimeError("SELinux must remain enforcing")
    run("mountpoint", "-q", "/nix")
    if Path("/nix").is_symlink() or not os.path.samefile("/nix", "/var/lib/nix"):
        raise RuntimeError("Unexpected /nix mount identity")
    info = Path("/nix").stat()
    if (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) != (0, 0, 0o755):
        raise RuntimeError("Unexpected /nix ownership or mode")
    if "ro" not in run("findmnt", "-n", "-o", "OPTIONS", "/").split(","):
        raise RuntimeError("Nix integration requires read-only root")


def accounts_conflict():
    groups = grp.getgrall()
    users = pwd.getpwall()
    names = {f"nixbld{i}" for i in range(1, 33)}
    return any(g.gr_name == "nixbld" or g.gr_gid == 30000 for g in groups) or any(
        u.pw_name in names or 30001 <= u.pw_uid <= 30032 for u in users)


def check_accounts():
    if grp.getgrnam("nixbld").gr_gid != 30000:
        raise RuntimeError("Build group changed")
    for index in range(1, 33):
        user = pwd.getpwnam(f"nixbld{index}")
        if (user.pw_uid, user.pw_gid) != (30000 + index, 30000):
            raise RuntimeError("Build-user identity changed")


def backing_mapping_present(listing):
    """Recognize the exact equivalence; never replace custom Nix rules."""
    present = False
    for line in listing.splitlines():
        fields = line.split()
        if fields == ["/var/lib/nix", "=", "/nix"]:
            present = True
        elif fields and fields[0].startswith(("/var/lib/nix", "/nix")):
            raise RuntimeError("Custom Nix SELinux mapping requires administrator review")
    return present


def prepare_backing_mapping():
    if not backing_mapping_present(run("semanage", "fcontext", "-l", "-C")):
        run("semanage", "fcontext", "-a", "-e", "/nix", "/var/lib/nix")


def secure_state_directory():
    STATE.mkdir(parents=True, mode=0o700, exist_ok=True)
    for path in (STATE.parent, STATE):
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise RuntimeError("Unsafe ownership-state directory")


def seed_config():
    target = Path("/etc/nix/nix.conf")
    target.parent.mkdir(exist_ok=True)
    info = target.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise RuntimeError("Unsafe configuration directory")
    seed_config_file(target, (RESOURCES / "nix.conf").read_bytes())


def health(state):
    check_accounts()
    if not stat.S_ISREG(Path("/etc/nix/nix.conf").lstat().st_mode):
        raise RuntimeError("Configuration is not a regular file")
    plan = json.loads((STATE / "plan.json").read_text())
    receipt = json.loads(Path("/nix/receipt.json").read_text())
    if digest(plan) != state["plan_sha256"] or not receipt_matches(plan, receipt):
        raise RuntimeError("Receipt does not match owned plan")
    if any(action["state"] != "Completed" for action in receipt["actions"]):
        raise RuntimeError("Receipt contains unfinished actions")
    binary = "/nix/var/nix/profiles/default/bin/nix"
    print(run(binary, "--version"))
    run("matchpathcon", "-V", str(Path(binary).resolve()))
    backing = "/var/lib/nix/" + str(Path(binary).resolve()).removeprefix("/nix/")
    run("matchpathcon", "-V", backing)
    if not backing_mapping_present(run("semanage", "fcontext", "-l", "-C")):
        raise RuntimeError("Persistent backing-store label equivalence is missing")
    run(binary, "store", "info", "--store", "daemon")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("initialize", "finalize", "status"))
    args = parser.parse_args()
    preflight()
    secure_state_directory()
    with locked(STATE):
        state = read_state(STATE)
        artifact_sha = hashlib.sha256(INSTALLER.read_bytes()).hexdigest()
        disposition = classify(state, store_empty=not any(Path("/nix").iterdir()),
                               accounts_conflict=accounts_conflict(), payload_sha256=artifact_sha)
        print(disposition, flush=True)
        if args.operation == "status":
            return
        if args.operation == "finalize":
            if state is None or state["phase"] not in {"validating", "complete"}:
                raise RuntimeError("Initialization has not reached validation")
            health(state)
            write_state(STATE, state | {"phase": "complete"})
            return
        if disposition == "validate":
            # A separate finalizer checks the daemon after systemd starts it.
            return
        if disposition not in {"fresh", "start"}:
            raise RuntimeError(
                f"Refusing automatic changes: {disposition}. "
                "Partial data and configuration have been retained. "
                "Guided manual repair is required; do not delete the store or "
                "ownership metadata, uninstall, or replay the installer."
            )
        architecture = {"aarch64": "aarch64-linux", "x86_64": "x86_64-linux"}[os.uname().machine]
        manifest = json.loads((RESOURCES / "artifacts.json").read_text())
        verify(INSTALLER, manifest["artifacts"][architecture])
        prepare_backing_mapping()
        seed_config()
        before = hashlib.sha256(Path("/etc/nix/nix.conf").read_bytes()).hexdigest()
        if state is None:
            raw = STATE / "upstream-plan.json"
            run(str(INSTALLER), "plan", "--out-file", str(raw), "linux", "--init", "none",
                "--no-start-daemon", "--no-modify-profile", "--skip-nix-conf")
            plan = adapt(json.loads(raw.read_text()))
            with (STATE / "plan.json").open("x") as output:
                json.dump(plan, output)
                output.flush()
                os.fsync(output.fileno())
            state = {"schema": 1, "phase": "prepared", "installer_sha256": artifact_sha,
                     "plan_sha256": digest(plan)}
            write_state(STATE, state)
        else:
            plan = json.loads((STATE / "plan.json").read_text())
            if digest(plan) != state["plan_sha256"]:
                raise RuntimeError("Owned plan changed")
        write_state(STATE, state | {"phase": "installing"})
        subprocess.run(["unshare", "--net", "--", str(INSTALLER), "install", "--no-confirm",
                        str(STATE / "plan.json")], check=True)
        if hashlib.sha256(Path("/etc/nix/nix.conf").read_bytes()).hexdigest() != before:
            raise RuntimeError("Administrator configuration changed during initialization")
        write_state(STATE, state | {"phase": "validating"})


if __name__ == "__main__":
    main()
