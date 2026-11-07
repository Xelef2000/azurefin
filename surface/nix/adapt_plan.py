#!/usr/bin/env python3
"""Narrow adapter for the pinned community installer's editable-plan API.

Azurefin owns mounts, configuration and daemon units. This is not a generic
plan sanitizer: reject drift before executing any installer action.
"""
import argparse
import copy
import json
from pathlib import Path

VERSION = "2.35.4"
SETTINGS = {
    "modify_profile": False,
    "nix_build_group_name": "nixbld",
    "nix_build_group_id": 30000,
    "nix_build_user_prefix": "nixbld",
    "nix_build_user_count": 32,
    "nix_build_user_id_base": 30000,
    "ssl_cert_file": None,
    "extra_conf": [],
    "force": False,
    "skip_nix_conf": True,
    "add_channel": False,
    "enable_flakes": False,
}
POLICY_PATH = "/etc/nix-installer/selinux/packages/nix.pp"


def adapt(plan):
    """Adapt a freshly generated plan, never a partial installation receipt."""
    result = copy.deepcopy(plan)
    expected_planner = {
        "planner": "linux", "settings": SETTINGS,
        "init": {"init": "None", "start_daemon": False},
    }
    if result.get("version") != VERSION or result.get("planner") != expected_planner:
        raise ValueError("Unexpected installer version or unsafe planner settings")
    actions = result["actions"]
    names = [item["action"]["action_name"] for item in actions]
    expected = ["create_directory", "provision_nix", "create_users_and_group",
                "configure_nix", "provision_selinux", "create_directory",
                "create_upstream_init_service", "remove_directory"]
    if names != expected:
        raise ValueError("Unexpected action list (an SELinux-capable target is required)")
    # Generated on target with /nix already mounted by Azurefin. Never create,
    # prune, or own the mount point in an installer uninstall receipt.
    mount = actions[0]
    if (mount["state"] != "Completed" or mount["action"]["path"] != "/nix"
            or mount["action"]["is_mountpoint"] is not True):
        raise ValueError("Generate the plan only after mounting persistent /nix")
    configure = actions[3]["action"]
    for field in ("place_nix_configuration", "configure_shell_profile", "setup_channels"):
        if configure.get(field, "missing") is not None:
            raise ValueError(f"Installer must not manage {field}")
    policy = actions[4]["action"]
    if policy["policy_path"] != "/usr/share/selinux/packages/nix.pp":
        raise ValueError("Unexpected SELinux policy destination")
    if not policy["policy_content"]:
        raise ValueError("Missing embedded SELinux policy")
    policy["policy_path"] = POLICY_PATH
    init = actions[6]["action"]["configure_init_service"]["action"]
    if init["init"] != "None" or init["start_daemon"]:
        raise ValueError("Installer must not own or start systemd units")
    if actions[5]["action"]["path"] != "/etc/tmpfiles.d":
        raise ValueError("Unexpected directory action")
    if actions[7]["action"]["path"] != "/nix/temp-install-dir":
        raise ValueError("Unexpected scratch cleanup")
    # Only omit actions for Azurefin-owned resources. Preserve upstream
    # provisioning, account creation, profile setup and per-action receipts.
    result["actions"] = [actions[i] for i in (1, 2, 3, 4, 7)]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = adapt(json.loads(args.input.read_text()))
    # Never replace an existing plan/receipt accidentally.
    with args.output.open("x") as output:
        json.dump(result, output, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()
