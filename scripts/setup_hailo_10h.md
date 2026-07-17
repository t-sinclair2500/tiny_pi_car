# Hailo-10H setup (Pi 5 + AI HAT+ 2 class device)

**Device on this robot:** PCIe `1e60:45c4` at `0001:01:00.0` (Hailo-10H).  
**OS today (host docs historically):** Bookworm notes remain for Path B.  
**Robot SD card now (2026-07-16):** fresh **Trixie** — use Path A (`hailo-h10-all`).  
Live probe: [docs/autonomy/PI_BRINGUP.md](../docs/autonomy/PI_BRINGUP.md).

Cross-checked against:
- https://www.raspberrypi.com/documentation/computers/ai.html (requires **Trixie** + `hailo-h10-all` for AI HAT+ 2)
- https://dev-public.hailo.ai/2026_04/Hailo10/ (HailoRT **5.3.0** debs fetchable without login)
- Research notes: [`docs/research/hailo-official-ecosystem.md`](../docs/research/hailo-official-ecosystem.md), [`docs/research/hailo-pi5-gotchas.md`](../docs/research/hailo-pi5-gotchas.md)

## Go / no-go (this machine, Bookworm)

| Action | Verdict | Why |
|--------|---------|-----|
| `sudo apt install hailo-h10-all` | **NO-GO** | Package **absent** from Bookworm apt |
| `sudo apt install hailo-all` (4.20) | **NO-GO** | Hailo-8 stack; wrong driver class (`hailo_pci` vs `hailo1x_pci`) |
| Upgrade OS → Trixie, then `apt install hailo-h10-all` | **GO (official)** | Trixie apt has `hailo-h10-all` **5.1.1** + `h10-hailort*` |
| Install cached HailoRT **5.3.0** debs on Bookworm | **GO (unofficial)** | debs downloaded; needs `dkms` + **reboot**; not Pi-blessed |
| Install Trixie `h10-*` debs on Bookworm | **NO-GO by default** | Built for Trixie; script refuses unless override |
| Reboot this prep pass | **NO** | Only after a real driver install |

`hailo-all` and `hailo-h10-all` **conflict** — never install both.

---

## Helper script (preferred)

```sh
# Status + ensure caches (safe; no install, no reboot)
./scripts/setup_hailo_10h.sh

# Refresh downloads only
./scripts/setup_hailo_10h.sh --download-only

# WHEN YOU APPROVE install on Bookworm (will demand typing INSTALL; then YOU reboot):
./scripts/setup_hailo_10h.sh --install bookworm-hailort-5.3
```

Caches (already populated on this robot):

| Path | Contents |
|------|----------|
| `.cache/hailo-debs/` | Hailo **5.3.0** + **5.1.1** runtime/driver/tappas + GenAI zoo + cp311/cp313 wheels |
| `.cache/hailo-debs/trixie-apt/` | Offline copy of Trixie `hailo-h10-all` 5.1.1 stack |
| `.cache/hailo-src/hailo-apps/` | Shallow clone of https://github.com/hailo-ai/hailo-apps |

---

## Path A (preferred long-term): Trixie + `hailo-h10-all`

Official Pi AI docs (2026): 64-bit **Trixie**, then:

```sh
sudo apt update
sudo apt full-upgrade -y
sudo rpi-eeprom-update -a
sudo reboot

sudo apt install dkms
sudo apt install hailo-h10-all
sudo reboot

hailortcli fw-control identify   # expect Device Architecture: HAILO10H
lsmod | grep hailo               # prefer hailo1x_pci
python3 -m playground.hailo_probe
```

**Warning:** Dist-upgrade Bookworm→Trixie can break unrelated robot services. Do it in a maintenance window with a backup / spare SD image. Not done in this prep pass.

Trixie package versions seen on `archive.raspberrypi.com` (2026-07-14): `hailo-h10-all` / `h10-hailort` / `h10-hailort-pcie-driver` **5.1.1**, `hailo-tappas-core` **5.1.0**.

---

## Path B: Stay on Bookworm + Hailo 5.3.0 debs (cached)

```sh
sudo apt install dkms raspberrypi-kernel-headers build-essential

# Or use the helper (recommended):
./scripts/setup_hailo_10h.sh --install bookworm-hailort-5.3

# Manual equivalent (driver FIRST):
cd .cache/hailo-debs
sudo apt install ./hailort-pcie-driver_5.3.0_all.deb
sudo apt install ./hailort_5.3.0_arm64.deb
sudo apt install ./hailo-tappas-core_5.3.0_arm64.deb

# ***** REBOOT REQUIRED *****
sudo reboot
```

After reboot:

```sh
lsmod | grep hailo
# If legacy hailo_pci wins the probe:
#   echo 'blacklist hailo_pci' | sudo tee /etc/modprobe.d/blacklist-hailo-pci.conf
#   sudo reboot

ls -l /dev/hailo0
hailortcli fw-control identify
# Bookworm Python 3.11 binding (venv):
#   .venv/bin/pip install .cache/hailo-debs/hailort-5.3.0-cp311-cp311-linux_aarch64.whl
python3 -m playground.hailo_probe
```

Driver package contents confirmed: includes `/lib/firmware/hailo/hailo10h/` and `hailo1x_pci` DKMS sources.

---

## Do NOT do this

```sh
sudo apt install hailo-all          # Bookworm 4.20 — wrong for Hailo-10H
sudo apt install hailo-dkms hailort # same generation
```

---

## Post-install verify

```sh
lspci -nn | grep -i hailo
lsmod | grep -i hailo
ls -l /dev/hailo*
command -v hailortcli && hailortcli fw-control identify
python3 -m playground.hailo_probe
```

## After runtime is up

1. Place **hailo10h** `.hef` files under `playground/vision/models/` (gitignored).
2. Wire detector adapter; keep unavailable fallback.
3. Optional: `cd .cache/hailo-src/hailo-apps && sudo ./install.sh` (needs working HailoRT first).

## References

- [docs/hailo.md](../docs/hailo.md)
- [docs/research/hailo-official-ecosystem.md](../docs/research/hailo-official-ecosystem.md)
- [docs/research/hailo-pi5-gotchas.md](../docs/research/hailo-pi5-gotchas.md)
- Pi AI software: https://www.raspberrypi.com/documentation/computers/ai.html
- HailoRT 5.3 docs: https://hailo.ai/developer-zone/documentation/hailort-v5-3-0/
