#!/usr/bin/env python3
"""Validate AUTOSAR ARXML interface contracts against generated C code."""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {"ar": "http://autosar.org/schema/r4.0"}
REPO = Path(__file__).resolve().parent.parent
violations = []


def find_param_value(root, def_suffix):
    """Find a parameter value by its DEFINITION-REF suffix."""
    for param in root.iter():
        def_ref = param.find("ar:DEFINITION-REF", NS)
        if def_ref is not None and def_ref.text and def_ref.text.endswith(def_suffix):
            val = param.find("ar:VALUE", NS)
            if val is not None and val.text:
                return val.text.strip()
    return None


def find_channel_names(root):
    """Extract all DIO channel SHORT-NAMEs from DioChannel containers."""
    channels = {}
    for container in root.iter(f"{{{NS['ar']}}}ECUC-CONTAINER-VALUE"):
        def_ref = container.find("ar:DEFINITION-REF", NS)
        if def_ref is not None and def_ref.text and def_ref.text.endswith("/DioChannel"):
            name_el = container.find("ar:SHORT-NAME", NS)
            if name_el is not None and name_el.text:
                channel_id = find_param_value(container, "DioChannelId")
                channels[name_el.text.strip()] = channel_id
    return channels


def check_can_baudrate():
    arxml = REPO / "MCAL/McalCfg/Can_EcucValues.arxml"
    c_file = REPO / "MCAL/McalGen/Can_PBcfg.c"
    if not arxml.exists() or not c_file.exists():
        return

    tree = ET.parse(arxml)
    arxml_baud = find_param_value(tree.getroot(), "CanControllerBaudRate")
    if not arxml_baud:
        return

    c_text = c_file.read_text()
    c_bauds = re.findall(r"\.CanControllerBaudRate\s*=\s*(\d+)", c_text)
    c_defaults = re.findall(r"\.CanControllerDefaultBaudrate\s*=\s*(\d+)", c_text)

    for val in c_bauds + c_defaults:
        if val != arxml_baud:
            violations.append(
                f"**CAN Baud Rate mismatch**: ARXML defines `{arxml_baud}`, "
                f"but C code has `{val}` in `{c_file.relative_to(REPO)}`"
            )


def check_can_dev_error():
    arxml = REPO / "MCAL/McalCfg/Can_EcucValues.arxml"
    h_file = REPO / "MCAL/McalGen/Can_Cfg.h"
    if not arxml.exists() or not h_file.exists():
        return

    tree = ET.parse(arxml)
    arxml_val = find_param_value(tree.getroot(), "CanDevErrorDetection")
    if not arxml_val:
        return

    expected = "STD_ON" if arxml_val.lower() == "true" else "STD_OFF"
    h_text = h_file.read_text()
    match = re.search(r"#define\s+CAN_DEV_ERROR_DETECT\s+(STD_ON|STD_OFF)", h_text)
    if match and match.group(1) != expected:
        violations.append(
            f"**CAN Dev Error Detection mismatch**: ARXML defines `{arxml_val}` "
            f"(expects `{expected}`), but C code has `{match.group(1)}` "
            f"in `{h_file.relative_to(REPO)}`"
        )


def check_dio_channels():
    arxml = REPO / "MCAL/McalCfg/Dio_EcucValues.arxml"
    h_file = REPO / "MCAL/McalGen/Dio_Cfg.h"
    if not arxml.exists() or not h_file.exists():
        return

    tree = ET.parse(arxml)
    arxml_channels = find_channel_names(tree.getroot())

    h_text = h_file.read_text()
    c_channels = dict(re.findall(r"#define\s+DioConf_DioChannel_(\w+)\s+(\d+)", h_text))

    arxml_names = set(arxml_channels.keys())
    c_names = set(c_channels.keys())

    for name in sorted(c_names - arxml_names):
        violations.append(
            f"**Phantom DIO channel**: `{name}` (ID={c_channels[name]}) exists in "
            f"`{h_file.relative_to(REPO)}` but is NOT defined in ARXML"
        )
    for name in sorted(arxml_names - c_names):
        violations.append(
            f"**Missing DIO channel**: `{name}` is defined in ARXML but missing "
            f"from `{h_file.relative_to(REPO)}`"
        )
    for name in sorted(arxml_names & c_names):
        if arxml_channels[name] and c_channels[name] != arxml_channels[name]:
            violations.append(
                f"**DIO channel ID mismatch**: `{name}` has ID `{arxml_channels[name]}` "
                f"in ARXML but `{c_channels[name]}` in C code"
            )


def main():
    check_can_baudrate()
    check_can_dev_error()
    check_dio_channels()

    print("## AUTOSAR Interface Contract Compliance Report\n")
    print("### Scope")
    print("- `MCAL/McalCfg/Can_EcucValues.arxml`")
    print("- `MCAL/McalCfg/Dio_EcucValues.arxml`")
    print("- `MCAL/McalGen/Can_PBcfg.c`")
    print("- `MCAL/McalGen/Can_Cfg.h`")
    print("- `MCAL/McalGen/Dio_Cfg.h`\n")

    if violations:
        print(f"### Findings ({len(violations)} violation(s))\n")
        for i, v in enumerate(violations, 1):
            print(f"{i}. {v}")
        print("\n### Result\n❌ **FAIL**")
        return 1
    else:
        print("### Findings\nNo violations detected.\n")
        print("### Result\n✅ **PASS**")
        return 0


if __name__ == "__main__":
    sys.exit(main())
