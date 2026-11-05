"""Fail-closed ownership/checkpoint primitives; not yet a host initializer.

Callers must verify root ownership of the state directory and the /nix bind
mount before using this module. Nothing here executes an installer or modifies
the store/accounts. A receipt is evidence, never permission for blind replay.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

SCHEMA = 1
PHASES = {"prepared", "installing", "validating", "complete"}
FIELDS = {"schema", "installer_sha256", "plan_sha256", "phase"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def validate(state):
    if not isinstance(state, dict) or set(state) != FIELDS:
        raise ValueError("Unrecognized ownership metadata")
    if type(state["schema"]) is not int or state["schema"] != SCHEMA:
        raise ValueError("Unsupported ownership schema; do not overwrite")
    if state["phase"] not in PHASES:
        raise ValueError("Unknown initialization phase")
    for field in ("installer_sha256", "plan_sha256"):
        if not isinstance(state[field], str) or not re.fullmatch(r"[0-9a-f]{64}", state[field]):
            raise ValueError("Invalid pinned artifact or plan digest")
    return state


def classify(state, *, store_empty, accounts_conflict, payload_sha256):
    """Classify only; even 'validate' requires actual runtime/daemon checks."""
    if state is None:
        return "fresh" if store_empty and not accounts_conflict else "foreign"
    validate(state)
    # Image upgrades must not reinstall/downgrade a previously completed runtime.
    if state["phase"] == "complete":
        return "validate"
    if state["installer_sha256"] != payload_sha256:
        return "needs-original-payload"
    if state["phase"] == "prepared" and store_empty and not accounts_conflict:
        return "start"
    if state["phase"] == "validating":
        return "validate"
    # Neither a stale receipt nor a missing one proves what SIGKILL interrupted.
    return "needs-reconciliation"


def receipt_matches(plan, receipt):
    """Allow state changes only, retaining every action argument and identity.

    This is a diagnostic comparison, NOT an authorization to resume actions.
    """
    def normalize(value):
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if isinstance(value, dict):
            if set(value) == {"action", "state"}:
                if value["state"] not in {"Uncompleted", "Progress", "Completed", "Skipped"}:
                    raise ValueError("Unknown receipt action state")
                return {"action": normalize(value["action"])}
            return {key: normalize(item) for key, item in value.items()}
        return value
    return normalize(plan) == normalize(receipt)


@contextmanager
def locked(directory):
    """The caller supplies a private, root-owned, non-symlink directory."""
    path = Path(directory) / "lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def read_state(directory):
    try:
        fd = os.open(Path(directory) / "state.json", os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    with os.fdopen(fd) as source:
        return validate(json.load(source))


def seed_config_file(target, contents):
    """Publish a complete default file without replacing an administrator file.

    The caller verifies the parent directory is trusted. A failed write never
    leaves a truncated default at the target name.
    """
    target = Path(target)
    if target.exists() or target.is_symlink():
        if not stat.S_ISREG(target.lstat().st_mode):
            raise ValueError("Existing configuration is not a regular file")
        return
    fd, temporary = tempfile.mkstemp(prefix=".nix-conf-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(contents)
            output.flush()
            os.fchmod(output.fileno(), 0o644)
            os.fsync(output.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            if not stat.S_ISREG(target.lstat().st_mode):
                raise ValueError("Concurrent configuration is not a regular file") from None
        dirfd = os.open(target.parent, os.O_DIRECTORY | os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        os.unlink(temporary)


def write_state(directory, state):
    """Atomic, fsynced checkpoint. Caller must hold locked(directory)."""
    validate(state)
    directory = Path(directory)
    fd, temporary = tempfile.mkstemp(prefix=".state-", dir=directory)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(state, output, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, directory / "state.json")
        dirfd = os.open(directory, os.O_DIRECTORY | os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
