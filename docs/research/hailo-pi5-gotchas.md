# Hailo on Pi 5 — community gotchas (MasterPi robot)

> **Install callout (this robot):** Do **not** `apt install hailo-all` on Bookworm for this HAT. Runtime is already up via HailoRT 5.3 — see **[docs/hailo.md](../hailo.md)** and **[scripts/setup_hailo_10h.md](../../scripts/setup_hailo_10h.md)**. The “Local baseline” table below is a **2026-07-14 pre-install snapshot** (outdated); footguns in later sections remain useful.

Research notes for bringing up the **Hailo-10H** (PCIe `1e60:45c4`) on this MasterPi stack
(Pi 5 + HiWonder expansion board UART + USB camera + mecanum/servos). Originally framed around the
2026-07-14 probe (device at Gen3 x1 before driver install).

Companion bring-up notes: [`docs/hailo.md`](../hailo.md). Hardware inventory:
[`docs/hardware.md`](../hardware.md).

---

## Local baseline (this robot, 2026-07-14)

| Check | Result |
| --- | --- |
| OS | Debian 12 **Bookworm** (`6.12.93+rpt-rpi-2712`) |
| PCIe | `0001:01:00.0` Hailo `1e60:45c4` (Hailo-10H) |
| Link | Gen3 x1 negotiated (`8.0 GT/s`) — EEPROM/HAT path already did its job |
| Driver | **not loaded** (`hailo_pci` / `hailo1x_pci` absent from `lsmod`) |
| Device node | **no** `/dev/hailo*` |
| Packages | **none** installed; Bookworm apt candidates are `hailo-all` / `hailort` / `hailo-dkms` **4.20.0** |
| `hailo-h10-all` | **not in Bookworm apt** (appears on Trixie / newer Pi AI docs) |
| UART config | `/boot/firmware/config.txt` has `dtparam=uart0=on` (docs prefer `dtoverlay=uart0-pi5`) |
| Camera | USB `32e6:9005` → `/dev/video0` (not CSI) |
| Thermals (idle) | ~50 °C, `throttled=0x0` |

**Implication:** PCIe hardware path is healthy. The remaining risk is installing the *wrong*
software stack for Hailo-10H on Bookworm, then fighting version / driver-class conflicts.

---

## 1. PCIe / firmware / EEPROM / `config.txt`

### What the community + official docs say

- **AI HAT+ / AI HAT+ 2** (soldered Hailo, HAT+ EEPROM): Gen3 is applied via the HAT EEPROM;
  you normally **do not** need `dtparam=pciex1_gen=3`. Official docs:
  [raspberrypi.com/documentation/computers/ai.html](https://www.raspberrypi.com/documentation/computers/ai.html).
- **AI Kit (M.2 HAT + module)**: Gen3 is **manual** (`raspi-config` → Advanced → PCIe Speed, or
  `dtparam=pciex1_gen=3` in `/boot/firmware/config.txt`).
- Keep Pi boot EEPROM / firmware current before blaming Hailo:
  `sudo rpi-eeprom-update -a` then reboot. Stale firmware is a recurring “device not seen” cause
  on fresh kits ([hailo-rpi5-examples install notes](https://github.com/hailo-ai/hailo-rpi5-examples/blob/main/doc/install-raspberry-pi5.md)).
- GPIO header must stay connected on AI HAT boards: 5 V + GND + ID EEPROM pins. EEPROM on the
  HAT ID bus is what auto-applies Gen3; without it you can fall back to Gen2 and lose throughput
  ([Hailo community GPIO guide](https://community.hailo.ai/t/using-the-raspberry-pi-gpios-with-the-hailo-ai-hat/11237)).

### Gold nuggets

- Pi 5 is **not formally Gen3-certified**, but RPT has qualified Hailo at Gen3; Gen2 works but
  larger models pay a PCIe cache / bandwidth penalty
  ([RPi forums AI Kit thread](https://forums.raspberrypi.com/viewtopic.php?t=371844)).
- Inference timeouts on an otherwise “healthy” Hailo-10H often track ASPM / Gen3 / cold-boot
  quirks; community threads recommend confirming Gen3 + sometimes `pcie_aspm=off`
  ([Hailo-10H timeout thread](https://community.hailo.ai/t/hailo-10h-on-raspberry-pi-ai-hat-2-times-out-during-inference-including-direct-hailortcli-run2/18868)).
- FFC seating errors look like “no PCIe device” — reseat before reinstalling packages.

### This robot

Already at Gen3 x1 with `1e60:45c4` visible → **do not chase Gen3 overlays first**. Prefer
software-stack correctness. After any HAT reseat / power work, re-check:

```sh
lspci -nn | rg -i hailo
sudo lspci -vv -s 0001:01:00.0 | rg -i 'LnkSta|LnkCap'
python3 -m playground.hailo_probe
```

---

## 2. `hailo-all` vs `hailo-h10-all` vs manual install

| Package / path | Targets | Notes |
| --- | --- | --- |
| `hailo-all` | Hailo-8 / Hailo-8L (AI Kit, AI HAT+) | Metapackage: driver + HailoRT + TAPPAS bits. On this Bookworm image: **4.20.0**. |
| `hailo-h10-all` | Hailo-10H (AI HAT+ 2) | Official Pi docs: **cannot coexist** with `hailo-all`. Not present in this Bookworm apt cache. |
| Manual `.deb` from Hailo | Matched driver + `hailort` + tappas | Used when apt lags (e.g. HailoRT 5.x for 10H). Install **driver first**, then runtime. |
| `dkms` | Required for modern installs | Skipping DKMS is the #1 cause of “library 4.23 / driver 4.20” mismatches. |

Official split: [AI software docs — note on packages](https://www.raspberrypi.com/documentation/computers/ai.html)
(*AI Kit / AI HAT+ → `hailo-all`; AI HAT+ 2 → `hailo-h10-all`*).

Community consensus for Hailo-10H:

- Need **`hailo1x_pci`** (not legacy `hailo_pci` alone) and HailoRT **≥ 5.x** for proper 10H
  support ([driver conflict report](https://community.hailo.ai/t/hailo-10h-fails-to-initialize-on-clean-raspberry-pi-os-install-due-to-legacy-hailo-pci-driver-conflict/18986);
  [hailo-apps expects driver ≥ 5.0.0 for hailo10h](https://community.hailo.ai/t/raspberry-trixie-error-with-guide-pi-5-ai-hat-2/18681)).
- Bookworm `hailo-all` 4.20 is a **Hailo-8-era** stack. Blind `apt install hailo-all` on a 10H
  is a known footgun (wrong firmware path / wrong module / probe failures).
- Prefer either: upgrade path to **Trixie + `hailo-h10-all`**, or manual Hailo-10 packages from
  Hailo’s public/dev feeds (example writeup:
  [system_setup.md](https://github.com/gregm123456/raspberry_pi_hailo_ai_services/blob/main/reference_documentation/system_setup.md)).

Always:

```sh
sudo apt install dkms          # before Hailo packages
sudo apt install <chosen meta or debs>
sudo reboot                    # required after PCIe driver change
hailortcli fw-control identify
```

---

## 3. Conflicts with other HATs / UART / cameras

### Electrical / GPIO (Hailo side)

AI HAT+ family typically consumes:

- 5 V / GND for supplemental power
- HAT ID EEPROM on the ID bus (BCM 0/1 / pins 27–28 in HAT+ terms; older writeups also stress
  not fighting the ID EEPROM during boot)

UART, SPI, PWM, and most application GPIOs stay free
([Sixfab AI HAT+ pinout notes](https://docs.sixfab.com/docs/ai-hat-plus-raspberry-pi-5-pinout-gpio);
[Hailo GPIO guide](https://community.hailo.ai/t/using-the-raspberry-pi-gpios-with-the-hailo-ai-hat/11237)).

So **UART to the HiWonder expansion board is not an electrical Hailo conflict** in the usual
HAT+ design. The risks are mechanical stacking, EEPROM clash with *another* HAT+, and power.

### Critical for MasterPi coexistence

| Subsystem | Risk with Hailo | Mitigation |
| --- | --- | --- |
| HiWonder expansion board (motors/servos/battery) | **Mechanical stack height** / header pass-through; both want the 40-pin header | Plan spacers / FFC clearance; confirm UART still maps to `/dev/ttyAMA0` after any HAT change |
| UART `/dev/ttyAMA0` | Software ownership (multiple MasterPi processes), not Hailo pins | Single owner; keep `dtoverlay=uart0-pi5` (or verified `uart0`) and **no** serial console on that port — see [`docs/hardware.md`](../hardware.md) |
| USB camera `32e6:9005` | No CSI lane fight with Hailo; **exclusive open** on `/dev/video0` | One camera broker; do not run `MasterPi/Camera.py` + `fswebcam` + autonomy grabber together |
| CSI cameras (if ever swapped in) | Ribbon routing under HAT heat sinks / standoffs | Attach camera before HAT when possible (Pi AI docs recommend this order) |
| Second HAT with EEPROM @ 0x50 | ID-bus conflict | Disable/desolder one EEPROM or manually load overlays ([RPi forums stacking](https://forums.raspberrypi.com/viewtopic.php?t=372508)) |
| NVMe / other PCIe | **Impossible** — one PCIe connector | Hailo owns PCIe; no dual accelerator + SSD on stock Pi 5 |

### Gold nuggets

- Stacking headers need enough Z-height for Hailo heatsink (often 14–17 mm pass-through).
- “GPIO free” ≠ “robot board fits.” MasterPi’s expansion board is the hard part, not the UART
  pinmux vs Hailo.

---

## 4. Power budget (Pi 5 8GB + Hailo + motors/servos)

Rough numbers from reviews / docs (order-of-magnitude, not a lab measurement on this chassis):

| Consumer | Typical / peak |
| --- | --- |
| Pi 5 SoC under load | up to ~8–10 W class |
| Hailo-10H / AI HAT+ 2 | ~2.5 W typ; vision ~3.5–4.5 W; gen-AI bursts higher (~3 W chip limit cited by reviewers) |
| USB camera | small, but still on 5 V rail |
| Mecanum motors + 5-DOF bus servos | **dominant** — battery/expansion board rails, not just USB-C PSU |

References: [Jeff Geerling AI HAT+ 2](https://www.jeffgeerling.com/blog/2026/raspberry-pi-ai-hat-2/),
[Hackster review (≈2.5 W draw)](https://www.hackster.io/news/gen-ai-on-your-raspberry-pi-a-hands-on-review-of-the-raspberry-pi-ai-hat-2-3c829a8894dd),
[power telemetry writeup](https://www.faceofit.com/raspberry-pi-ai-hat-2-compatibility/).

### Robot-specific risks

- Bench bring-up: prefer **official 27W / 5 V 5 A** USB-C PSU for Pi+Hailo alone.
- On battery: HiWonder board already warns on low voltage (`board.get_battery()`). Hailo
  inference + wheel/arm current spikes can brown-out the Pi even if motors “still twitch.”
- AI HAT draws supplemental current from the **GPIO 5 V pins** — same rail family the
  expansion stack cares about. Do not treat Hailo as “PCIe-only powered.”
- Safe bring-up order: install/verify Hailo **with wheels lifted / arm disabled**, then add
  motion under low speed with voltage logging.

---

## 5. Thermal throttling

- Pi 5 **does not throttle PCIe separately**; CPU thermal throttle can still cut host
  preprocess / pipeline FPS
  ([RPi forums](https://forums.raspberrypi.com/viewtopic.php?t=391518)).
- Hailo HAT heatsink + Pi Active Cooler are both recommended; cooler + HAT stacking is a
  common question ([cooling thread](https://forums.raspberrypi.com/viewtopic.php?t=382684)).
- Enclosed robot chassis + continuous YOLO + motor heat → expect earlier throttle than desktop
  demos. Watch `vcgencmd measure_temp` and `vcgencmd get_throttled` during first long runs.
- Under-FPS vs model-zoo numbers on Pi 5 is often **PCIe x1**, not thermals
  ([FPS discussion](https://forums.raspberrypi.com/viewtopic.php?t=396633)).

---

## 6. Multi-process Hailo device access (`/dev/h1x-0` on this stack)

Default rule: **one process owns the device**. Second `VDevice` →
`HAILO_OUT_OF_PHYSICAL_DEVICES` / device busy.

On HailoRT 5.x / Hailo-10H here the node is **`/dev/h1x-0`** (legacy Hailo-8 docs say `/dev/hailo0`).

Options community uses:

1. **Single Hailo worker process** in our autonomy design (preferred for MasterPi — matches
   “one camera broker / one detector” already planned in [`docs/autonomy/perception.md`](../autonomy/perception.md)).
2. **HailoRT Multi-Process Service (MPS)** — enable `hailort` / `hailort-service`, set
   `multi_process_service=True` + shared `group_id`
   ([ROS2 busy-device thread](https://community.hailo.ai/t/switching-between-two-ros-2-nodes-using-hailo-on-rpi5-device-still-reported-as-busy/18740);
   [MPS / gRPC pitfalls](https://community.hailo.ai/t/issue-with-hailo-gstreamer-pipeline-on-recomputer-ai-r2000-multi-process-service-error/13395)).
3. Custom device manager that serializes inference
   ([example architecture](https://github.com/gregm123456/raspberry_pi_hailo_ai_services/blob/main/device_manager/README.md)).

Also: orphaned Python processes hold the node after Ctrl-C — check with `fuser` / `lsof` on
`/dev/h1x-0` (or legacy `/dev/hailo0`) before assuming a driver bug.

---

## 7. Version matrix after `apt upgrade`

Classic failure:

```text
Driver version (4.20.0) is different from library version (4.23.0)
HAILO_INVALID_DRIVER_VERSION
```

Seen repeatedly when:

- Kernel still has an older in-tree / leftover `hailo_pci.ko`
- DKMS was **not** installed before `hailo-all`
- Manual `.deb` mixed with apt packages
- Trixie/Bookworm guides crossed

Useful threads:

- [4.23 vs 4.20 mismatch — install `dkms` then reinstall](https://community.hailo.ai/t/hailo-version-mismatch-4-23-vs-4-20/18373)
- [Wrong driver after dpkg — purge leftovers](https://community.hailo.ai/t/rasperry-pi-hailort-install-wrong-driver-version/17060)
- [Ubuntu/RPi purge recipe](https://community.hailo.ai/t/rpi5-ubuntu-24-04lts-hailort-4-22/16537)
- [Legacy `hailo_pci` vs `hailo1x_pci` probe fight on 10H](https://community.hailo.ai/t/hailo-10h-fails-to-initialize-on-clean-raspberry-pi-os-install-due-to-legacy-hailo-pci-driver-conflict/18986)
- [Cleanup guide](https://community.hailo.ai/t/raspberry-pi-hailo-pci-driver-conflict-issue-solution/19022)
- [RPi forum apt hell / held packages](https://forums.raspberrypi.com/viewtopic.php?t=385489)

Recovery pattern:

```sh
sudo apt purge hailo-all hailo-h10-all hailort hailofw hailo-tappas-core hailort-pcie-driver hailo-dkms || true
# remove leftover modules for current kernel (hailo_pci and hailo1x_pci)
sudo depmod -a
sudo apt install dkms
# then install ONE coherent stack (h10 meta OR matched Hailo .debs)
sudo reboot
```

Pin versions with `apt-mark hold` if a working matrix is found (Pi docs show hold examples for
older vision demos).

After every kernel upgrade: confirm DKMS rebuilt modules for `uname -r`.

---

## 8. Link bag (gold nuggets)

| Topic | Link |
| --- | --- |
| Official Pi AI software (packages, Gen3, Trixie) | https://www.raspberrypi.com/documentation/computers/ai.html |
| Hailo rpi5 examples install (PSU, cooler, Gen3) | https://github.com/hailo-ai/hailo-rpi5-examples/blob/main/doc/install-raspberry-pi5.md |
| `hailo-all` vs `hailo-h10-all`, reboot, `hailo1x_pci` | https://community.hailo.ai/t/raspberry-trixie-error-with-guide-pi-5-ai-hat-2/18681 |
| Hailo-10H init fail / dual driver class | https://community.hailo.ai/t/hailo-10h-fails-to-initialize-on-clean-raspberry-pi-os-install-due-to-legacy-hailo-pci-driver-conflict/18986 |
| Driver leftover cleanup | https://community.hailo.ai/t/raspberry-pi-hailo-pci-driver-conflict-issue-solution/19022 |
| Version mismatch 4.23/4.20 + DKMS | https://community.hailo.ai/t/hailo-version-mismatch-4-23-vs-4-20/18373 |
| Inference timeout / ASPM / Gen3 | https://community.hailo.ai/t/hailo-10h-on-raspberry-pi-ai-hat-2-times-out-during-inference-including-direct-hailortcli-run2/18868 |
| Multi-process / device busy | https://community.hailo.ai/t/switching-between-two-ros-2-nodes-using-hailo-on-rpi5-device-still-reported-as-busy/18740 |
| GPIO / EEPROM / Gen3 auto | https://community.hailo.ai/t/using-the-raspberry-pi-gpios-with-the-hailo-ai-hat/11237 |
| HAT stacking / power / single PCIe | https://forums.raspberrypi.com/viewtopic.php?t=372508 |
| Gen3 qualification commentary | https://forums.raspberrypi.com/viewtopic.php?t=371844 |
| Cooling with HAT | https://forums.raspberrypi.com/viewtopic.php?t=382684 |
| AI HAT+ 2 power / review context | https://www.jeffgeerling.com/blog/2026/raspberry-pi-ai-hat-2/ |
| Hailo-10H setup options (apt vs Hailo debs) | https://github.com/gregm123456/raspberry_pi_hailo_ai_services/blob/main/reference_documentation/system_setup.md |

---

## Install-risk checklist for THIS robot

Use before any `apt install` / `.deb` work. Goal: keep expansion-board motion safe and avoid a
half-broken Hailo-8 stack on a Hailo-10H.

### Pre-flight

- [x] Confirm `1e60:45c4` Gen3 x1; runtime up — node is **`/dev/h1x-0`** (not `hailo0`).
- [x] Stack chosen: Bookworm + HailoRT **5.3** Path B. Still **never** install Bookworm `hailo-all` 4.20.
- [ ] Before any *future* driver swap: snapshot `dpkg-query -W 'hailo*'`; `uname -r`; copy of `/boot/firmware/config.txt`.
- [ ] Update EEPROM/firmware (`rpi-eeprom-update`) on a maintenance window, not mid-demo.

### Coexistence (MasterPi)

- [ ] Mechanically verify AI HAT + HiWonder expansion board + camera cable clearance.
- [ ] After reboot, confirm `/dev/ttyAMA0` still exists and a **dry** board open works
      (wheels up, no motion loop).
- [ ] Keep UART overlay correct (`dtoverlay=uart0-pi5` preferred); ensure no login console on
      that UART.
- [ ] Single owner for camera `/dev/video0` and single owner for Hailo **`/dev/h1x-0`**
      (playground probe / one detector worker).
- [ ] Do not run `MasterPi.py` / `rpc_server.py` / playground motion concurrently with bring-up.

### Power / thermal / motion safety

- [ ] First Hailo verify on **bench PSU (27W-class)**, actuators disabled / wheels lifted.
- [ ] Log battery voltage before enabling motors with inference running.
- [ ] Confirm Active Cooler + Hailo heatsink airflow in the chassis.
- [ ] Watch `vcgencmd get_throttled` during a sustained detect loop.
- [ ] Motion scripts: low speed, explicit stop, short timeouts (project rule).

### Post-install verify

- [x] `lsmod | rg hailo` → **`hailo1x_pci`** (done on this robot)
- [x] `ls -l /dev/h1x-0` (HailoRT 5.x node; not `/dev/hailo0`)
- [x] `hailortcli fw-control identify` → HAILO10H FW 5.3.0
- [x] `python3 -m playground.hailo_probe` → `ready: True`
- [ ] After any later `apt full-upgrade` / kernel bump: re-run the verify block; hold pins if
      needed.

### Explicit anti-patterns on this machine

- [ ] Mixing `hailo-all` and `hailo-h10-all`.
- [ ] Installing Hailo-8-only / `hailo8` driver branch against `1e60:45c4`.
- [ ] Skipping reboot after PCIe driver install.
- [ ] Opening Hailo from MasterPi RPC **and** playground detector at once without MPS.
- [ ] Assuming Gen3/`config.txt` is the bug when PCIe already enumerates at Gen3 with no driver.
