#!/usr/bin/env python3
"""Transform a generated installer GRUB config for the 13-inch Surface only.

Reads stdin and writes stdout. The caller must stage the matching kernel DTB
at DTB_PATH in the ISO, and update both the ISO and EFI-image configurations.
This does not configure the installed system's bootloader.
"""

import re
import sys
import argparse

DTB_PATH = "/images/dtbs/qcom/x1e80100-microsoft-romulus13.dtb"
# Diagnostic only: explicitly load the early display/GLINK/mailbox providers,
# instead of relying solely on udev to discover the included modules.
EARLY_DISPLAY_DRIVERS = (
    "qcom-spmi-pmic", "nvmem_qcom_spmi_sdam", "qcom-pbs", "leds-qcom-lpg",
    "qrtr", "qrtr-smd", "qcom_pd_mapper", "qcom_q6v5_pas",
    "qcom-cpucp-mbox", "pmic-glink", "pmic-glink-altmode",
    "aux-hpd-bridge", "ps883x", "dispcc-x1e80100", "gpucc-x1e80100",
    "phy_qcom_edp", "panel_edp", "pwm_bl", "msm", "hid-generic",
)


def patch_config(config: str, diagnostic: bool = False) -> str:
    if re.search(r"^\s*devicetree\s", config, re.MULTILINE):
        raise ValueError("Config already selects a device tree; review it manually")
    lines = []
    count = 0
    for line in config.splitlines():
        match = re.match(r"^(\s*)(linux(?:efi)?)\s+(.+)$", line)
        if not match:
            lines.append(line)
            continue
        indent, command, arguments = match.groups()
        args = arguments.split()
        if args[0] != "/images/pxeboot/vmlinuz":
            raise ValueError(f"Unexpected installer kernel path: {args[0]}")
        args = [arg for arg in args if arg != "inst.text"]
        required = ["clk_ignore_unused", "pd_ignore_unused"]
        if "inst.rescue" not in args:
            required.append("inst.graphical")
        args.extend(arg for arg in required if arg not in args)
        lines.append(f"{indent}{command} {' '.join(args)}")
        lines.append(f"{indent}devicetree {DTB_PATH}")
        count += 1
    if not count:
        raise ValueError("No installer kernel entries found")
    result = "\n".join(lines) + "\n"
    if diagnostic:
        kernel = re.search(r"^\s*linux(?:efi)?\s+(.+)$", result, re.MULTILINE)
        initrd = re.search(r"^\s*initrd(?:efi)?\s+(.+)$", result, re.MULTILINE)
        if not initrd or initrd.group(1).strip() != "/images/pxeboot/initrd.img":
            raise ValueError("Unexpected or missing installer initrd")
        args = [arg for arg in kernel.group(1).split()
                if arg not in ("quiet", "rhgb", "splash", "rd.debug")
                and not arg.startswith(("panic=", "rd.break=", "consoleblank=",
                                        "loglevel=", "systemd.log_level="))]
        args += ["loglevel=6", "systemd.log_level=info", "consoleblank=0",
                 "systemd.log_target=console", "systemd.show_status=1",
                 "rd.plymouth=0", "plymouth.enable=0", "panic=0"]
        # Preserve the normal entries and all power/thermal protections.
        for title, entry_id, extra in (
            ("Surface diagnostic: readable boot", "romulus-diagnostic", ""),
            ("Surface diagnostic: pause before udev", "romulus-pre-udev", " rd.break=pre-udev"),
            ("Surface diagnostic: preload display providers", "romulus-preload-display",
             " rd.driver.pre=" + ",".join(EARLY_DISPLAY_DRIVERS)),
        ):
            result += (f"\nmenuentry '{title}' --id {entry_id} {{\n"
                       f"  linux {' '.join(args)}{extra}\n"
                       f"  devicetree {DTB_PATH}\n"
                       "  initrd /images/pxeboot/initrd.img\n}\n")
        result += "set default=romulus-preload-display\n"
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnostic", action="store_true")
    options = parser.parse_args()
    try:
        result = patch_config(sys.stdin.read(), diagnostic=options.diagnostic)
    except ValueError as error:
        sys.exit(str(error))
    sys.stdout.write(result)
