#!/usr/bin/env bash
# Hailo-10H (AI HAT+ 2) prep / install helper for tiny_pi_car.
#
# Default: NON-destructive — download packages only. Never installs hailo-all.
# Install paths require --install and an explicit stack choice.
#
# Usage:
#   ./scripts/setup_hailo_10h.sh                  # status + ensure downloads
#   ./scripts/setup_hailo_10h.sh --download-only  # refresh caches, exit
#   ./scripts/setup_hailo_10h.sh --install bookworm-hailort-5.3
#   ./scripts/setup_hailo_10h.sh --install trixie-h10-offline
#
# After any driver install: REBOOT REQUIRED (script will refuse to reboot itself).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE_DIR="${HAILO_CACHE_DIR:-$REPO_ROOT/.cache/hailo-debs}"
SRC_DIR="${HAILO_SRC_DIR:-$REPO_ROOT/.cache/hailo-src}"
TRI_DIR="$CACHE_DIR/trixie-apt"
DEV_BASE_530="https://dev-public.hailo.ai/2026_04/Hailo10"
DEV_BASE_511="https://dev-public.hailo.ai/2025_12/Hailo10"
APT_TRI_BASE="http://archive.raspberrypi.com/debian"

MODE="status"
INSTALL_STACK=""
ASSUME_YES=0

red() { printf '\033[31m%s\033[0m\n' "$*"; }
yel() { printf '\033[33m%s\033[0m\n' "$*"; }
grn() { printf '\033[32m%s\033[0m\n' "$*"; }

usage() {
  sed -n '1,20p' "$0" | tail -n +2
  cat <<EOF

Flags:
  --download-only              Fetch debs/wheels/hailo-apps; do not install
  --install <stack>            Install from local cache (see stacks below)
  -y, --yes                    Skip interactive confirm on --install
  --help                       This help

Install stacks:
  bookworm-hailort-5.3         Hailo dev-public 5.3.0 (driver+runtime+tappas)
                               Prefer on Bookworm; still experimental vs Trixie apt.
  trixie-h10-offline           Pi Trixie hailo-h10-all 5.1.1 debs from local cache
                               ONLY safe on a Trixie OS (or after you accept risk).

NEVER:
  apt install hailo-all        # Bookworm 4.20 = Hailo-8 stack; wrong for 10H
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --download-only) MODE="download"; shift ;;
    --install)
      MODE="install"
      INSTALL_STACK="${2:-}"
      [[ -n "$INSTALL_STACK" ]] || { red "--install needs a stack name"; usage; exit 2; }
      shift 2
      ;;
    -y|--yes) ASSUME_YES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) red "Unknown arg: $1"; usage; exit 2 ;;
  esac
done

os_codename() {
  . /etc/os-release
  echo "${VERSION_CODENAME:-unknown}"
}

have_pkg() { apt-cache show "$1" >/dev/null 2>&1; }

print_status() {
  local codename
  codename="$(os_codename)"
  echo "=== Host ==="
  echo "OS:       $(. /etc/os-release; echo "$PRETTY_NAME")"
  echo "codename: $codename"
  echo "kernel:   $(uname -r)"
  echo "python:   $(python3 --version 2>&1)"
  echo "PCI:      $(lspci -nn 2>/dev/null | grep -i hailo || echo '(none)')"
  echo "lsmod:    $(lsmod | grep -i hailo || echo '(no hailo modules)')"
  if compgen -G '/dev/hailo*' >/dev/null 2>&1; then
    ls -l /dev/hailo*
  else
    echo "nodes:    (no /dev/hailo*)"
  fi
  echo
  echo "=== Bookworm apt (this machine) ==="
  apt-cache policy hailo-all hailort hailo-dkms hailo-h10-all 2>/dev/null | sed 's/^/  /' || true
  if have_pkg hailo-h10-all; then
    grn "hailo-h10-all IS visible in apt (unexpected on pure Bookworm)."
  else
    yel "hailo-h10-all NOT in apt on this OS (expected on Bookworm)."
  fi
  echo
  echo "=== Go / no-go ==="
  if [[ "$codename" == "bookworm" ]]; then
    red "NO-GO: official 'sudo apt install hailo-h10-all' on Bookworm (package absent)."
    red "NO-GO: 'sudo apt install hailo-all' (candidate 4.20 = wrong generation for 10H)."
    yel "GO (unofficial): install matched HailoRT 5.x debs already cached under:"
    echo "         $CACHE_DIR"
    yel "GO (official): upgrade OS to Trixie, then apt install hailo-h10-all (needs reboot)."
  elif [[ "$codename" == "trixie" ]]; then
    grn "GO: sudo apt install dkms && sudo apt install hailo-h10-all  (then REBOOT)."
  else
    yel "Unknown codename '$codename' — check Pi AI docs before installing."
  fi
  echo "REBOOT: required after PCIe driver install; this script will NOT reboot."
  echo
  echo "=== Cache ==="
  du -sh "$CACHE_DIR" "$SRC_DIR" 2>/dev/null || true
  ls -1 "$CACHE_DIR"/*.deb "$CACHE_DIR"/*.whl 2>/dev/null | sed 's|^|  |' || echo "  (empty)"
  ls -1 "$TRI_DIR"/*.deb 2>/dev/null | sed 's|^|  |' || true
  [[ -d "$SRC_DIR/hailo-apps/.git" ]] && echo "  hailo-apps: $SRC_DIR/hailo-apps" || echo "  hailo-apps: missing"
}

fetch() {
  local url="$1" out="$2"
  if [[ -f "$out" && -s "$out" ]]; then
    echo "have $(basename "$out")"
    return 0
  fi
  echo "GET $url"
  curl -fL --max-time 300 -o "${out}.partial" "$url"
  mv "${out}.partial" "$out"
  ls -lh "$out"
}

download_all() {
  mkdir -p "$CACHE_DIR" "$TRI_DIR" "$SRC_DIR"

  echo "=== Download Hailo 5.3.0 (dev-public) ==="
  fetch "$DEV_BASE_530/hailort-pcie-driver_5.3.0_all.deb" "$CACHE_DIR/hailort-pcie-driver_5.3.0_all.deb"
  fetch "$DEV_BASE_530/hailort_5.3.0_arm64.deb" "$CACHE_DIR/hailort_5.3.0_arm64.deb"
  fetch "$DEV_BASE_530/hailo-tappas-core_5.3.0_arm64.deb" "$CACHE_DIR/hailo-tappas-core_5.3.0_arm64.deb"
  fetch "$DEV_BASE_530/hailo_gen_ai_model_zoo_5.3.0_arm64.deb" "$CACHE_DIR/hailo_gen_ai_model_zoo_5.3.0_arm64.deb"
  # Bookworm = Python 3.11; Trixie often 3.13
  fetch "$DEV_BASE_530/hailort-5.3.0-cp311-cp311-linux_aarch64.whl" \
    "$CACHE_DIR/hailort-5.3.0-cp311-cp311-linux_aarch64.whl"
  fetch "$DEV_BASE_530/hailort-5.3.0-cp313-cp313-linux_aarch64.whl" \
    "$CACHE_DIR/hailort-5.3.0-cp313-cp313-linux_aarch64.whl"

  echo "=== Download Hailo 5.1.1 (dev-public) ==="
  fetch "$DEV_BASE_511/hailort-pcie-driver_5.1.1_all.deb" "$CACHE_DIR/hailort-pcie-driver_5.1.1_all.deb"
  fetch "$DEV_BASE_511/hailort_5.1.1_arm64.deb" "$CACHE_DIR/hailort_5.1.1_arm64.deb"
  fetch "$DEV_BASE_511/hailo-tappas-core_5.1.0_arm64.deb" "$CACHE_DIR/hailo-tappas-core_5.1.0_arm64.deb"
  fetch "$DEV_BASE_511/hailo_gen_ai_model_zoo_5.1.1_arm64.deb" "$CACHE_DIR/hailo_gen_ai_model_zoo_5.1.1_arm64.deb"

  echo "=== Download Trixie apt H10 packages (offline inventory) ==="
  local tmp_pkgs
  tmp_pkgs="$(mktemp)"
  curl -fsSL "$APT_TRI_BASE/dists/trixie/main/binary-arm64/Packages.gz" | gzip -dc >"$tmp_pkgs"
  python3 - "$tmp_pkgs" "$TRI_DIR" "$APT_TRI_BASE" <<'PY'
import os, sys, urllib.request
pkgs_path, outdir, base = sys.argv[1:4]
want = {
    "hailo-h10-all", "h10-hailort", "h10-hailort-pcie-driver",
    "python3-h10-hailort", "hailo-tappas-core", "python3-hailo-tappas",
    "rpicam-apps-hailo-postprocess",
}
seen = set()
for block in open(pkgs_path).read().split("\n\n"):
    meta = {}
    for line in block.splitlines():
        if line.startswith("Package: "):
            meta["Package"] = line[9:]
        elif line.startswith("Filename: "):
            meta["Filename"] = line[10:]
    pkg = meta.get("Package")
    if pkg in want and pkg not in seen:
        seen.add(pkg)
        url = base.rstrip("/") + "/" + meta["Filename"]
        out = os.path.join(outdir, os.path.basename(meta["Filename"]))
        if os.path.exists(out) and os.path.getsize(out) > 0:
            print("have", os.path.basename(out))
            continue
        print("GET", url)
        urllib.request.urlretrieve(url, out + ".partial")
        os.rename(out + ".partial", out)
print("trixie packages:", ", ".join(sorted(seen)))
PY
  rm -f "$tmp_pkgs"

  if [[ -d "$SRC_DIR/hailo-apps/.git" ]]; then
    echo "hailo-apps already present"
  else
    git clone --depth 1 https://github.com/hailo-ai/hailo-apps.git "$SRC_DIR/hailo-apps"
  fi

  (cd "$CACHE_DIR" && sha256sum *.deb *.whl >SHA256SUMS.txt 2>/dev/null || true)
  (cd "$TRI_DIR" && sha256sum *.deb >../SHA256SUMS-trixie.txt 2>/dev/null || true)
  grn "Downloads ready under $CACHE_DIR (gitignored via .cache/)."
}

confirm_install() {
  local msg="$1"
  yel "$msg"
  red "This changes kernel modules / system packages. A REBOOT will be required afterward."
  red "This script will NOT reboot. Do not install hailo-all."
  if [[ "$ASSUME_YES" -eq 1 ]]; then
    return 0
  fi
  read -r -p "Type INSTALL to continue: " ans
  [[ "$ans" == "INSTALL" ]] || { echo "Aborted."; exit 1; }
}

ensure_dkms() {
  if ! dpkg -s dkms >/dev/null 2>&1; then
    yel "Installing dkms + build deps (safe, no Hailo packages)..."
    sudo apt-get update
    sudo apt-get install -y dkms build-essential raspberrypi-kernel-headers || \
      sudo apt-get install -y dkms build-essential linux-headers-generic || true
  fi
}

install_bookworm_530() {
  local codename
  codename="$(os_codename)"
  download_all
  confirm_install "Install HailoRT 5.3.0 from $CACHE_DIR on OS=$codename?"

  if dpkg -l | grep -E '^ii\s+(hailo-all|hailo-dkms|hailort)\s' | grep -q '4\.20'; then
    red "Found Hailo 4.20 packages installed — purge them first (wrong for 10H)."
    exit 1
  fi

  ensure_dkms
  # Driver FIRST, then runtime, then tappas (community / Hailo order).
  sudo apt-get install -y "$CACHE_DIR/hailort-pcie-driver_5.3.0_all.deb"
  sudo apt-get install -y "$CACHE_DIR/hailort_5.3.0_arm64.deb"
  sudo apt-get install -y "$CACHE_DIR/hailo-tappas-core_5.3.0_arm64.deb"

  if [[ -f "$CACHE_DIR/hailort-5.3.0-cp311-cp311-linux_aarch64.whl" ]] && \
     python3 -c 'import sys; raise SystemExit(0 if sys.version_info[:2]==(3,11) else 1)'; then
    yel "Optional: pip install the cp311 wheel into your venv after reboot:"
    echo "  .venv/bin/pip install $CACHE_DIR/hailort-5.3.0-cp311-cp311-linux_aarch64.whl"
  fi

  red "=== REBOOT REQUIRED ==="
  red "Do NOT reboot from automation unless you intend to. Next human command:"
  echo "  sudo reboot"
  echo "Then:"
  echo "  lsmod | grep hailo          # expect hailo1x_pci"
  echo "  ls -l /dev/hailo0"
  echo "  hailortcli fw-control identify"
  echo "  python3 -m playground.hailo_probe"
  yel "If hailo_pci loads instead of hailo1x_pci:"
  echo "  echo 'blacklist hailo_pci' | sudo tee /etc/modprobe.d/blacklist-hailo-pci.conf"
  echo "  sudo reboot"
}

install_trixie_offline() {
  local codename
  codename="$(os_codename)"
  download_all
  if [[ "$codename" != "trixie" ]]; then
    red "OS is '$codename', not trixie. Offline hailo-h10-all debs are built for Trixie."
    red "Installing them on Bookworm can pull broken deps or leave a half-broken stack."
    confirm_install "OVERRIDE: install Trixie H10 debs on $codename anyway?"
  else
    confirm_install "Install Trixie hailo-h10-all stack from $TRI_DIR?"
  fi
  ensure_dkms
  sudo apt-get install -y \
    "$TRI_DIR/h10-hailort-pcie-driver_5.1.1_all.deb" \
    "$TRI_DIR/h10-hailort_5.1.1_arm64.deb" \
    "$TRI_DIR/hailo-tappas-core_5.1.0_arm64.deb" \
    "$TRI_DIR/python3-h10-hailort_5.1.1-1_arm64.deb" \
    "$TRI_DIR/python3-hailo-tappas_5.1.0_arm64.deb" \
    "$TRI_DIR/rpicam-apps-hailo-postprocess_1.12.0-1_arm64.deb" \
    "$TRI_DIR/hailo-h10-all_5.1.1_all.deb" || true
  red "=== REBOOT REQUIRED ==="
  echo "  sudo reboot"
}

case "$MODE" in
  status)
    print_status
    download_all
    print_status
    ;;
  download)
    download_all
    print_status
    ;;
  install)
    case "$INSTALL_STACK" in
      bookworm-hailort-5.3) install_bookworm_530 ;;
      trixie-h10-offline) install_trixie_offline ;;
      *)
        red "Unknown stack: $INSTALL_STACK"
        usage
        exit 2
        ;;
    esac
    ;;
esac
