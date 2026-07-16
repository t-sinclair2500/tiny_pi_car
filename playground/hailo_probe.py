"""Report Hailo-10H readiness (PCIe, driver, /dev/h1x-*, Python bindings)."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

HAILO_10H_ID = "1e60:45c4"


def _run(*command: str) -> str:
    try:
        return subprocess.run(command, text=True, capture_output=True, timeout=5, check=False).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _module_loaded(modules: str, *names: str) -> bool:
    low = modules.lower()
    return any(name.lower() in low for name in names)


def _apt_policy(pkg: str) -> str:
    out = _run("apt-cache", "policy", pkg)
    installed = candidate = None
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("Installed:"):
            installed = s
        elif s.startswith("Candidate:"):
            candidate = s
    if not out.strip():
        return "n/a (no package)"
    return f"{installed or 'Installed: ?'}; {candidate or 'Candidate: ?'}"


def _device_nodes() -> list[str]:
    """Hailo-10H uses /dev/h1x-*; legacy Hailo-8 uses /dev/hailo*."""
    root = Path("/dev")
    nodes: list[str] = []
    for pattern in ("h1x*", "hailo*"):
        nodes.extend(str(p) for p in root.glob(pattern))
    return sorted(set(nodes))


def probe() -> dict[str, object]:
    lspci = _run("lspci", "-nn")
    lspci_l = lspci.lower()
    device_nodes = _device_nodes()
    modules = _run("lsmod")
    driver_loaded = _module_loaded(modules, "hailo1x_pci", "hailo_pci", "hailo")
    py_hailort = importlib.util.find_spec("hailort") is not None
    py_platform = importlib.util.find_spec("hailo_platform") is not None
    py_ok = py_hailort or py_platform
    for alt in ("hailo",):
        if importlib.util.find_spec(alt) is not None:
            py_ok = True
    hailortcli = shutil.which("hailortcli")
    identify = ""
    if hailortcli:
        identify = _run(hailortcli, "fw-control", "identify").strip()[:500]
    arch_ok = "HAILO10H" in identify.upper() or HAILO_10H_ID in lspci_l
    ready = bool(device_nodes) and py_ok and driver_loaded and arch_ok
    return {
        "model": "Hailo-10H" if HAILO_10H_ID in lspci_l else "unknown/not detected",
        "pcie_detected": HAILO_10H_ID in lspci_l,
        "pcie_id": HAILO_10H_ID,
        "pcie_line": next((ln.strip() for ln in lspci.splitlines() if "1e60" in ln.lower()), ""),
        "driver_loaded": driver_loaded,
        "driver_modules_hint": "hailo1x_pci (H10 → /dev/h1x-*) or hailo_pci (legacy 8 → /dev/hailo*)",
        "device_nodes": device_nodes,
        "python_hailo_platform": py_platform,
        "python_hailort": py_hailort,
        "hailortcli": hailortcli,
        "fw_identify_snip": identify or None,
        "apt_hailo_all_candidate": _apt_policy("hailo-all"),
        "apt_hailo_h10_all_candidate": _apt_policy("hailo-h10-all"),
        "warning": None
        if ready
        else (
            "Hailo not ready. Need hailo1x_pci + /dev/h1x-* (or /dev/hailo*) + Python hailo_platform. "
            "Do NOT install Bookworm hailo-all 4.20. See scripts/setup_hailo_10h.md"
        ),
        "ready": ready,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    args = parser.parse_args()
    result = probe()
    if args.json:
        print(json.dumps(result, indent=2))
        return
    for key, value in result.items():
        print(f"{key}: {value}")
    if not result["ready"]:
        print("Next step: scripts/setup_hailo_10h.md — no inference will be attempted.")


if __name__ == "__main__":
    main()
