#!/usr/bin/python3
"""Explicit, console-based prototype run by Kickstart %pre, before partitioning."""
import os
from pathlib import Path
import re
import subprocess
import sys
import json
import tempfile
import traceback
from contextlib import contextmanager


class Tee:
    """Keep console diagnostics in both Anaconda's log and the USB workspace."""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for stream in self.streams:
            stream.write(text)
            stream.flush()
        return len(text)

    def flush(self):
        for stream in self.streams:
            stream.flush()


def usb_partitions(devices):
    for disk in devices:
        if disk.get("type") != "disk" or disk.get("tran") != "usb":
            continue
        name = Path(disk["name"]).name
        if not re.fullmatch(r"sd[a-z]+", name):
            continue
        for part in disk.get("children", []):
            if part.get("type") == "part" and part.get("fstype") in ("vfat", "exfat", "ntfs", "ntfs3", "ext4"):
                yield part["name"], name


@contextmanager
def usb_msi_files(workspace=None, workspace_disk=None):
    devices = json.loads(subprocess.check_output(
        ["lsblk", "--json", "--paths", "-o", "NAME,TYPE,TRAN,FSTYPE"], text=True))["blockdevices"]
    mounts = []
    files = []
    try:
        if workspace is not None:
            # %pre already mounted our verified workspace read-write. A second
            # read-only filesystem mount can be rejected; only read its files.
            files.extend((path, workspace_disk) for path in msi_files(workspace))
        for device, disk in usb_partitions(devices):
            if disk == workspace_disk:
                continue
            mount = Path(tempfile.mkdtemp(prefix="azurefin-msi-", dir="/run"))
            result = subprocess.run(["mount", "-o", "ro,nosuid,nodev,noexec", device, str(mount)],
                                    capture_output=True, text=True)
            if result.returncode:
                print(f"Cannot read {device}: {result.stderr.strip()}")
                mount.rmdir()
                continue
            mounts.append(mount)
            files.extend((path, disk) for path in msi_files(mount))
        yield files
    finally:
        for mount in reversed(mounts):
            result = subprocess.run(["umount", str(mount)], capture_output=True, text=True)
            if result.returncode == 0:
                mount.rmdir()
            else:
                print(f"Could not unmount MSI source {mount}: {result.stderr.strip()}")


def msi_files(root):
    # A writable installer workspace can also carry the MSI after flashing.
    # Search only two explicit locations, never recurse through arbitrary data.
    directories = [root]
    firmware = root / "firmware"
    if firmware.is_dir() and not firmware.is_symlink():
        directories.append(firmware)
    for directory in directories:
        for path in sorted(directory.iterdir()):
            if not path.is_symlink() and path.is_file() and path.suffix.lower() == ".msi":
                yield path


def open_console(path):
    # Buffered r+ uses BufferedRandom, which requires seek(). Character devices
    # need separate one-way streams; pass the reader explicitly to subprocesses.
    writer = open(path, "w", buffering=1)
    try:
        reader = open(path, "r", buffering=1)
    except BaseException:
        writer.close()
        raise
    return reader, writer


def bluetooth_address(value):
    value = value.strip().upper()
    if not value:
        return None
    if not re.fullmatch(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", value) or value in (
            "00:00:00:00:00:00", "FF:FF:FF:FF:FF:FF"):
        raise ValueError("Enter the factory Bluetooth address as six colon-separated hexadecimal pairs.")
    return value


def confirm_download():
    while True:
        answer = input("Download the Microsoft MSI and prepare firmware? [yes/no]: ").strip().lower()
        if answer in ("yes", "y"):
            print("Download approved. Starting preparation.")
            return
        if answer in ("no", "n", "q"):
            raise SystemExit("Cancelled; Anaconda will not proceed.")
        print("No confirmation received. Enter yes to proceed, or no/q to cancel.")


def prompt_bluetooth_address():
    print("Optional: use the Bluetooth public address reported by Windows, not the Wi-Fi MAC.")
    while True:
        try:
            return bluetooth_address(input("Bluetooth MAC address (Enter to skip): "))
        except ValueError as error:
            print(error)


def kickstart(payload, disk, source_disk=None, bluetooth_mac=None):
    address = bluetooth_address(bluetooth_mac or "")
    bluetooth_command = (f"azurefin-extract-firmware --bluetooth-address {address}\n"
                         if address else "")
    disks = list(dict.fromkeys([disk] + ([source_disk] if source_disk else [])))
    if not all(re.fullmatch(r"sd[a-z]+", name) for name in disks):
        raise ValueError("Unexpected external disk name")
    if not re.fullmatch(r"/run/azurefin-work/runs/azurefin-provision\.[A-Za-z0-9]+/container", payload):
        raise ValueError("Unexpected prepared payload path")
    return f'''# Generated only after successful firmware preparation.
ignoredisk --drives={','.join(disks)}
ostreecontainer --url={payload} --transport=oci
%post --erroronfail --log=/var/log/azurefin-provision-post.log
set -eu
python3 /usr/libexec/azurefin-installer-fix-fstab.py
{bluetooth_command}# Bluetooth address is written only to this installed system, not the OCI image.
# The private result has no public update source. Automatic updates remain
# masked by the payload; never switch to the firmware-free public base.
bootc switch --mutate-in-place --transport registry localhost/azurefin:local-provisioned
%end
'''


def prepared_path(line, runs):
    value = line.removeprefix("PAYLOAD_READY: ").strip()
    path = Path(value)
    if path.name != "container" or path.parent.parent != runs:
        raise ValueError("Preparation returned a path outside its workspace")
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Prepared payload must not be a symlink")
    if (path.parent / "READY").read_text().strip() != value:
        raise ValueError("Preparation success marker does not match")
    for name in ("index.json", "oci-layout"):
        if not (path / name).is_file():
            raise ValueError("Incomplete OCI payload")
    return value


def main():
    if os.geteuid() != 0 or len(sys.argv) != 2:
        raise SystemExit("Run from the test installer's Kickstart pre-script")
    disk = sys.argv[1]
    root = Path("/run/azurefin-work")
    source = Path(os.environ.get("AZUREFIN_INSTALLER_SOURCE", str(root)))
    output = Path("/run/azurefin-prepared.ks")
    if output.exists():
        raise SystemExit("A prepared Kickstart already exists; refusing to overwrite")
    # Validate before download, not just when rendering the final Kickstart.
    kickstart("/run/azurefin-work/runs/azurefin-provision.validation/container", disk)
    # Use a separate VT so Anaconda's tmux client cannot consume our input.
    console_in, console = open_console("/dev/tty8")
    sys.stdin = console_in
    persistent = (root / "launcher.log").open("a", buffering=1)
    sys.stdout = sys.stderr = Tee(console, sys.__stderr__, persistent)
    subprocess.run(["chvt", "8"], check=True)
    print("\nAzurefin firmware preparation — experimental installer")
    print("Use USB Ethernet to download firmware, or a USB drive containing the MSI.")
    print("The same installer SSD works: copy the MSI to AZUREFIN_WORK/firmware after flashing.")
    tools = source / "support/firmware-tools"
    supported_msis = subprocess.check_output([
        "python3", str(tools / "firmware-policy.py"),
        str(tools / "firmware-policy.json"), "list-msis"], text=True)
    print("Supported MSIs (first is used for downloads):\n" + supported_msis.strip())
    print("The external installer SSD is workspace only and will be excluded from installation.")
    print("No target disks are changed until you later confirm installation in Anaconda.")
    while True:
        choice = input("1: download over Ethernet; 2: MSI on USB; q: cancel: ").strip().lower()
        if choice in ("1", "2"):
            break
        if choice == "q":
            raise SystemExit("Cancelled; Anaconda will not proceed.")
    bluetooth_mac = prompt_bluetooth_address()
    if choice == "1":
        input("Plug in Ethernet, wait for it to connect, then press Enter.")
        confirm_download()
        payload = prepare(root, source=source)
        source_disk = None
    else:
        while True:
            if input("Put the MSI in the drive's top-level or firmware folder. Enter to scan, q to cancel: ").strip().lower() == "q":
                raise SystemExit("Cancelled; Anaconda will not proceed.")
            with usb_msi_files(root, disk) as files:
                if not files:
                    print("No MSI found. Use AZUREFIN_WORK/firmware on this SSD, or a USB drive's top-level/firmware folder.")
                    continue
                for number, (path, source_disk) in enumerate(files, 1):
                    print(f"{number}: {path.name!r} on {source_disk}")
                selected = input("Choose the file number (Enter to rescan): ").strip()
                if not selected.isdigit() or not 1 <= int(selected) <= len(files):
                    continue
                msi, source_disk = files[int(selected) - 1]
                payload = prepare(root, msi, source=source)
                break
    with output.open("x") as stream:
        stream.write(kickstart(payload, disk, source_disk, bluetooth_mac))
    print("Firmware preparation complete. Starting graphical Anaconda.")
    subprocess.run(["chvt", "1"], check=True)


def prepare(root, msi=None, source=None):
    source = root if source is None else source
    expected = (source / "base-image-id").read_text().strip()
    if not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ValueError("Invalid pinned base image ID")
    runs = root / "runs"
    runs.mkdir(exist_ok=True)
    payload = None
    command = ["bash", str(source / "support/28-prepare-installer-payload.sh"),
               str(source / "base-oci"), expected, str(runs)]
    if msi is not None:
        command.append(str(msi))
    with subprocess.Popen(command,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as process:
        for line in process.stdout:
            print(line, end="", flush=True)
            if line.startswith("PAYLOAD_READY: "):
                payload = prepared_path(line, runs)
        if process.wait() != 0 or payload is None:
            raise RuntimeError("Firmware preparation failed; installation will not proceed. Logs remain on the workspace.")
    return payload


if __name__ == "__main__":
    try:
        main()
    except SystemExit as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except (EOFError, KeyboardInterrupt):
        print("Console input ended; installation will not proceed.", file=sys.stderr)
        sys.exit(1)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
