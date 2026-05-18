#!/usr/bin/env python3
"""
EC (Embedded Controller) reset utility for Surface Laptop 7.

Sends a reset command to the Surface Aggregator Module (SAM) to recover
a stuck embedded controller — most commonly needed when the trackpad or
keyboard becomes unresponsive after suspend/resume.

Usage: sudo python3 ec_reboot.py [--force]
"""

import argparse
import os
import struct
import sys
import time


SAM_SYSFS_BASE = "/sys/bus/platform/devices"
SURFACE_AGGREGATOR_DRIVER = "surface_aggregator"


def find_sam_device():
    """Return the sysfs path of the Surface Aggregator device, or None."""
    try:
        for entry in os.scandir(SAM_SYSFS_BASE):
            link = os.path.join(entry.path, "driver")
            if os.path.islink(link):
                target = os.readlink(link)
                if SURFACE_AGGREGATOR_DRIVER in target:
                    return entry.path
    except FileNotFoundError:
        pass
    return None


def find_sam_hub():
    """Return the sysfs path of the SAM hub device (for sending requests)."""
    hub_path = "/sys/bus/surface_aggregator/devices/sam:hub:01"
    if os.path.exists(hub_path):
        return hub_path

    try:
        base = "/sys/bus/surface_aggregator/devices"
        for entry in os.scandir(base):
            if "hub" in entry.name.lower():
                return entry.path
    except FileNotFoundError:
        pass
    return None


def reset_via_module_reload():
    """Attempt EC reset by reloading the surface_aggregator kernel module."""
    import subprocess
    print("[*] Attempting EC reset via surface_aggregator module reload...")

    result = subprocess.run(
        ["modprobe", "-r", "surface_aggregator_registry"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"    Warning: could not unload surface_aggregator_registry: {result.stderr.strip()}")

    result = subprocess.run(
        ["modprobe", "-r", "surface_aggregator"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"    Warning: could not unload surface_aggregator: {result.stderr.strip()}")
        return False

    time.sleep(1)

    result = subprocess.run(
        ["modprobe", "surface_aggregator"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"    Error: could not reload surface_aggregator: {result.stderr.strip()}")
        return False

    result = subprocess.run(
        ["modprobe", "surface_aggregator_registry"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"    Warning: could not reload surface_aggregator_registry: {result.stderr.strip()}")

    time.sleep(2)
    print("[+] Module reloaded — EC should be responsive now.")
    return True


def reset_via_sysfs(sam_path):
    """Attempt EC reset via sysfs reset attribute if exposed by the driver."""
    reset_path = os.path.join(sam_path, "reset")
    if os.path.exists(reset_path):
        print(f"[*] Writing reset to {reset_path}...")
        try:
            with open(reset_path, "w") as f:
                f.write("1\n")
            print("[+] Reset signal sent.")
            return True
        except OSError as e:
            print(f"    Error: {e}")
    return False


def main():
    parser = argparse.ArgumentParser(description="Reset the Surface Laptop 7 embedded controller")
    parser.add_argument("--force", action="store_true",
                        help="Force reset even if SAM device not found via sysfs")
    args = parser.parse_args()

    if os.geteuid() != 0:
        print("Error: must be run as root (use sudo).")
        sys.exit(1)

    print("Surface Laptop 7 EC reset utility")
    print("----------------------------------")

    sam_path = find_sam_device()

    if sam_path:
        print(f"[+] Found SAM device at {sam_path}")
        if reset_via_sysfs(sam_path):
            return

    if sam_path is None and not args.force:
        print("[!] Surface Aggregator Module device not found in sysfs.")
        print("    Is the surface_aggregator module loaded?")
        print("    Run with --force to attempt module reload anyway.")
        sys.exit(1)

    if reset_via_module_reload():
        sys.exit(0)
    else:
        print("[!] EC reset failed. You may need to reboot.")
        sys.exit(1)


if __name__ == "__main__":
    main()
