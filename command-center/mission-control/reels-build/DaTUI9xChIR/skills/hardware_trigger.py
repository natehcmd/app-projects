"""
hardware_trigger.py
--------------------

Sends a short text command to a locally-attached hardware device over a
serial (USB) connection — e.g. an Arduino/ESP32 driving a servo or
solenoid for a DIY gadget (the "web shooter" style mechanism from the
reel this repo was built for).

This module only ever talks to a serial port on the machine it runs on.
It has no networking, no ability to reach anyone else's device, and no
bot-detection-evasion behavior of any kind.

Protocol (intentionally tiny, designed to match a simple Arduino sketch):
    We send a single line: "<DEVICE>:<ACTION>\n"
    e.g.  "WEB_SHOOTER:FIRE\n"
    and expect a single line back, e.g. "OK\n" or "ERR <reason>\n".

Environment variables:
    JARVIS_SERIAL_PORT   e.g. "/dev/tty.usbmodem14101" (macOS) or "COM5" (Windows)
    JARVIS_SERIAL_BAUD   defaults to 9600

If pyserial isn't installed, or no port is configured, or --dry-run is
passed, the command is only printed/simulated — never silently pretended
to have physically happened.
"""

from __future__ import annotations

import os
import re


class HardwareError(Exception):
    pass


def _normalize_device_name(device: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", device.upper()).strip("_")


def send_hardware_command(device: str, action: str, dry_run: bool = False) -> str:
    device_id = _normalize_device_name(device)
    action_id = action.upper()
    port = os.environ.get("JARVIS_SERIAL_PORT")
    baud = int(os.environ.get("JARVIS_SERIAL_BAUD", "9600"))

    if dry_run or not port:
        reason = "requested" if dry_run else "no JARVIS_SERIAL_PORT set"
        return f"[DRY RUN, {reason}] Would send '{device_id}:{action_id}' over serial"

    try:
        import serial  # pyserial
    except ImportError as e:
        raise HardwareError(
            "pyserial is required for real (non-dry-run) hardware control. "
            "Install it with: pip install pyserial"
        ) from e

    line = f"{device_id}:{action_id}\n".encode("utf-8")

    try:
        with serial.Serial(port, baud, timeout=3) as ser:
            ser.write(line)
            reply = ser.readline().decode("utf-8", errors="replace").strip()
    except Exception as e:  # serial.SerialException and friends
        raise HardwareError(f"Serial communication failed on {port}: {e}") from e

    if not reply:
        raise HardwareError(f"No response from device on {port} (timed out).")
    if reply.upper().startswith("ERR"):
        raise HardwareError(f"Device reported an error: {reply}")

    return f"Sent '{device_id}:{action_id}' -> device replied: {reply}"
