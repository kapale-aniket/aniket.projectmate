"""Low-battery emergency save + shutdown for long scrapes."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import threading

DEFAULT_CRITICAL_BATTERY_PERCENT = 3
SHUTDOWN_DELAY_SECONDS = 45

_lock = threading.Lock()
_shutdown_armed = False
_runtime_percent = None


def normalize_shutdown_percent(value, default=DEFAULT_CRITICAL_BATTERY_PERCENT):
    try:
        percent = int(value)
    except (TypeError, ValueError):
        percent = int(default)
    return max(1, min(99, percent))


def set_critical_percent(percent):
    global _runtime_percent
    _runtime_percent = normalize_shutdown_percent(percent)


def get_critical_percent():
    if _runtime_percent is not None:
        return normalize_shutdown_percent(_runtime_percent)

    env_val = os.environ.get("TERRA_BATTERY_SHUTDOWN_PERCENT")
    if env_val not in (None, ""):
        return normalize_shutdown_percent(env_val)

    for path in _settings_candidate_paths():
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            power = data.get("power") or {}
            if "shutdown_percent" in power:
                return normalize_shutdown_percent(power.get("shutdown_percent"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue

    return DEFAULT_CRITICAL_BATTERY_PERCENT


def _settings_candidate_paths():
    paths = []
    data_dir = os.environ.get("TERRA_DATA_DIR") or os.environ.get("LINKEDIN_DATA_DIR")
    if data_dir:
        paths.append(os.path.join(data_dir, "app_settings.json"))
    here = os.path.abspath(os.path.dirname(__file__))
    roots = [
        os.path.abspath(os.path.join(here, "..", "..", "..", "..", "data", "linkedin")),
        os.path.abspath(os.path.join(here, "..", "..", "..", "data", "linkedin")),
    ]
    for root in roots:
        paths.append(os.path.join(root, "app_settings.json"))
    return paths


def get_battery_status():
    system = platform.system().lower()
    if system == "windows":
        return _windows_battery()
    if system == "linux":
        return _linux_battery()
    return {"percent": None, "plugged": None, "has_battery": False}


def is_critical_unplugged(status=None, threshold=None):
    status = status or get_battery_status()
    if not status or not status.get("has_battery"):
        return False
    percent = status.get("percent")
    plugged = status.get("plugged")
    if percent is None or plugged is None:
        return False
    if plugged:
        return False
    limit = normalize_shutdown_percent(
        threshold if threshold is not None else get_critical_percent()
    )
    return int(percent) < limit


def _windows_battery():
    try:
        import ctypes
        from ctypes import wintypes

        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", wintypes.BYTE),
                ("BatteryFlag", wintypes.BYTE),
                ("BatteryLifePercent", wintypes.BYTE),
                ("SystemStatusFlag", wintypes.BYTE),
                ("BatteryLifeTime", wintypes.DWORD),
                ("BatteryFullLifeTime", wintypes.DWORD),
            ]

        status = SYSTEM_POWER_STATUS()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            return {"percent": None, "plugged": None, "has_battery": False}

        no_battery = bool(status.BatteryFlag & 128)
        percent_raw = int(status.BatteryLifePercent)
        percent = None if percent_raw > 100 else percent_raw
        ac = int(status.ACLineStatus)
        plugged = True if ac == 1 else False if ac == 0 else None
        has_battery = (not no_battery) and percent is not None
        return {"percent": percent, "plugged": plugged, "has_battery": has_battery}
    except Exception:
        return {"percent": None, "plugged": None, "has_battery": False}


def _linux_battery():
    base = "/sys/class/power_supply"
    try:
        names = os.listdir(base)
    except OSError:
        return {"percent": None, "plugged": None, "has_battery": False}

    bat_dirs = [n for n in names if n.upper().startswith("BAT")]
    if not bat_dirs:
        return {"percent": None, "plugged": None, "has_battery": False}

    bat = os.path.join(base, bat_dirs[0])
    percent = None
    try:
        with open(os.path.join(bat, "capacity"), "r", encoding="utf-8") as handle:
            percent = int(handle.read().strip())
    except (OSError, ValueError):
        percent = None

    plugged = None
    for name in names:
        upper = name.upper()
        if not (upper.startswith("AC") or upper.startswith("ADP") or "MAINS" in upper):
            continue
        try:
            with open(os.path.join(base, name, "online"), "r", encoding="utf-8") as handle:
                plugged = handle.read().strip() == "1"
                break
        except OSError:
            continue

    if plugged is None:
        try:
            with open(os.path.join(bat, "status"), "r", encoding="utf-8") as handle:
                st = handle.read().strip().lower()
                if st == "charging":
                    plugged = True
                elif st in {"discharging", "not charging"}:
                    plugged = False
        except OSError:
            pass

    return {
        "percent": percent,
        "plugged": plugged,
        "has_battery": percent is not None,
    }


def request_system_shutdown(reason="Low battery — jobs saved"):
    global _shutdown_armed
    with _lock:
        if _shutdown_armed:
            return False
        _shutdown_armed = True

    delay = max(15, int(SHUTDOWN_DELAY_SECONDS))
    msg = (reason or "Low battery")[:200]
    system = platform.system().lower()
    try:
        if system == "windows":
            subprocess.Popen(
                ["shutdown", "/s", "/t", str(delay), "/f", "/c", msg],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        elif system == "linux":
            subprocess.Popen(
                ["shutdown", "-h", f"+{max(1, delay // 60)}", msg],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif system == "darwin":
            subprocess.Popen(
                ["osascript", "-e", f'display notification "{msg}" with title "Low battery"'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.Popen(
                ["shutdown", "-h", f"+{max(1, delay // 60)}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            print(f"*** Shutdown not supported on this OS ({system}). ***", file=sys.stderr)
            return False
        print(f"*** System shutdown scheduled in {delay}s — {msg} ***", flush=True)
        return True
    except Exception as exc:
        print(f"*** Could not schedule shutdown: {exc} ***", flush=True)
        with _lock:
            _shutdown_armed = False
        return False


def format_status(status=None):
    status = status or get_battery_status()
    if not status or not status.get("has_battery"):
        return "no battery / unknown"
    plugged = status.get("plugged")
    plug = "AC" if plugged else "battery" if plugged is False else "?"
    return f"{status.get('percent')}% ({plug})"


CRITICAL_BATTERY_PERCENT = DEFAULT_CRITICAL_BATTERY_PERCENT
