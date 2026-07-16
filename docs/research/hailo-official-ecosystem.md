# Hailo-10H / Raspberry Pi AI HAT+ 2 — official ecosystem notes

> **STATUS (ops vs research, 2026-07-15):** Path B **done** on this robot (Bookworm + HailoRT 5.3, `/dev/h1x-0`, `ready: True`). Do **not** treat `sudo apt install hailo-all` below as our bring-up — that is Hailo-8 **4.20**. Trixie + `hailo-h10-all` is optional later. SSOT: [docs/autonomy/CURRENT_STATE.md](../autonomy/CURRENT_STATE.md) · [docs/hailo.md](../hailo.md).

**Date:** 2026-07-14  
**Hardware context:** Pi 5 8GB + PCIe Hailo-10H, PCI ID `1e60:45c4` confirmed on this machine.  
**Goal lens:** house-roaming robot + reliable object pickup (vision first; GenAI optional).  
**Scope:** official Raspberry Pi + Hailo docs/packages/repos. Timeboxed research.

Legend: **FACT** = verified from official docs/apt/GitHub; **LOCAL** = measured on this Pi; **UNCERTAIN** = community or incomplete; **SPECULATION** = useful idea, not a claim.

---

## 1. Exact product naming

| Name | What it is | Notes |
|------|------------|--------|
| **Hailo-10H** | NPU silicon / PCIe device | Official chip name. PCI vendor `1e60`, device `45c4`. Architecture string: `HAILO10H` / compile arch `hailo10h`. |
| **Raspberry Pi AI HAT+ 2** | Official Pi accessory board | On-board Hailo-10H + **8 GB LPDDR4X** on the HAT. Marketed as 40 TOPS **(INT4)**. |
| **AI HAT+** (no “2”) | Previous Pi accessory | Hailo-**8L** (13 TOPS INT8) or Hailo-**8** (26 TOPS INT8). No on-HAT DRAM for LLMs. |
| **AI Kit** | M.2 HAT+ + Hailo-8L module | EOL / not recommended for new designs. Same SW path as AI HAT+ (`hailo-all`). |
| **“H-10” / “H10”** | Informal shorthand | Appears in package prefixes (`h10-hailort`, `hailo-h10-all`). Not a separate product SKU. |

**FACT:** Do not conflate “AI HAT+” with “AI HAT+ 2”. Different chips, different apt metapackages, different GenAI capability.

**Sources:**  
- https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html  
- https://www.raspberrypi.com/documentation/computers/ai.html  
- Product brief: https://pip-assets.raspberrypi.com/categories/1319-raspberry-pi-ai-hat-2/documents/RP-009655-MM-4-raspberry-pi-ai-hat-plus-2-product-brief.pdf  
- News: https://www.raspberrypi.com/news/introducing-the-raspberry-pi-ai-hat-plus-2-generative-ai-on-raspberry-pi-5/

**LOCAL:** `lspci -nn` shows `1e60:45c4` at `0001:01:00.0`. OS is **Bookworm** (`Debian 12`), kernel `6.12.93+rpt-rpi-2712` aarch64.

---

## 2. Official install path (Pi OS, aarch64)

### 2.1 What Raspberry Pi documents today

Official AI software page: https://www.raspberrypi.com/documentation/computers/ai.html

Documented prerequisites (as of this research):

1. Raspberry Pi 5 + **64-bit Raspberry Pi OS** — docs now say **Trixie**, not Bookworm.  
2. Update OS + EEPROM, install DKMS, install the **correct** metapackage, reboot, verify.

```bash
sudo apt update
sudo apt full-upgrade -y
sudo rpi-eeprom-update -a
sudo reboot

sudo apt install dkms
# AI Kit / AI HAT+ (Hailo-8 / 8L):
sudo apt install hailo-all
# AI HAT+ 2 (Hailo-10H):
sudo apt install hailo-h10-all
sudo reboot

hailortcli fw-control identify
# optional:
dmesg | grep -i hailo
lspci -nnk | grep -A3 -i hailo
```

**FACT:** `hailo-all` and `hailo-h10-all` **conflict / cannot co-exist** (explicit note in Pi docs; Trixie packages declare `Conflicts:` on each other).

**FACT (AI HAT+ / HAT+ 2):** PCIe Gen 3 is applied automatically; manual `dtparam=pciex1_gen=3` is **AI Kit only**.

### 2.2 Trixie apt reality (verified against archive.raspberrypi.com)

On **trixie/main arm64**, relevant packages include:

| Package | Version (seen) | Role |
|---------|----------------|------|
| `hailo-h10-all` | 5.1.1 | Metapackage for Hailo-**10** |
| `h10-hailort` | 5.1.1 | Runtime (conflicts with `hailort`) |
| `h10-hailort-pcie-driver` | 5.1.1 | PCIe driver + FW (conflicts with `hailort-pcie-driver`) |
| `python3-h10-hailort` | (via metapackage) | Python bindings for H10 stack |
| `hailo-tappas-core` | 5.1.0 | GStreamer / postprocess core |
| `rpicam-apps-hailo-postprocess` | ≥ 1.10.0 | Camera post-process plugins |
| `hailo-all` | 5.1.1 | Metapackage for Hailo-**8** (`Depends: hailort >= 4.23…`) |
| `hailort` / `hailort-pcie-driver` | 4.23.0 | Hailo-8 path only |

`hailo-h10-all` depends on:  
`h10-hailort`, `h10-hailort-pcie-driver`, `hailo-tappas-core`, `rpicam-apps-hailo-postprocess`, `python3-h10-hailort`, `python3-hailo-tappas`.

### 2.3 Bookworm apt reality on *this* machine (critical)

**LOCAL FACT:** On Bookworm `archive.raspberrypi.com`, `apt-cache` exposes **`hailo-all` 4.20.0** (+ `hailort`/`hailo-dkms` 4.20) and **does not** expose `hailo-h10-all`, `h10-hailort`, or `h10-hailort-pcie-driver`.

So the **documented** AI HAT+ 2 one-liner (`apt install hailo-h10-all`) is **not available from Bookworm Pi apt today**. Official docs have moved the supported OS story toward **Trixie**.

| Path | Status for Hailo-10H on Bookworm |
|------|-----------------------------------|
| `sudo apt install hailo-h10-all` | **Not in Bookworm apt (LOCAL)** |
| `sudo apt install hailo-all` (4.20) | **Wrong generation** for 10H (Hailo-8 metapackage / 4.x stack) |
| Hailo `dev-public.hailo.ai` `.deb`s (5.1.1 / 5.3.0) | **Viable unofficial-on-Pi but official-from-Hailo** path (see §2.4) |
| Upgrade OS to Trixie, then `hailo-h10-all` | **Official Pi path** |

**Do not** follow the older Bookworm Hailo-8 recipe (`hailo-dkms` + `hailort` 4.20) for this HAT — community reports require HailoRT **≥ 5.0** and the **`hailo1x_pci`** driver family for 10H. **`docs/hailo.md` is now the verified Path-B bring-up** (HailoRT 5.3); ignore any older “install hailo-all 4.20” memories.

### 2.4 Hailo-published Debian packages (alternative / newer)

Hailo ships aarch64 debs under `https://dev-public.hailo.ai/…/Hailo10/` (versions observed in community writeups: **5.1.1**, **5.3.0**). Example pattern (versions change; verify listing):

```bash
# Example only — confirm exact filenames/versions on the server or Developer Zone
wget https://dev-public.hailo.ai/2026_04/Hailo10/hailort-pcie-driver_5.3.0_all.deb
wget https://dev-public.hailo.ai/2026_04/Hailo10/hailort_5.3.0_arm64.deb
wget https://dev-public.hailo.ai/2026_04/Hailo10/hailo-tappas-core_5.3.0_arm64.deb
sudo apt install ./hailort-pcie-driver_5.3.0_all.deb
sudo apt install ./hailort_5.3.0_arm64.deb
sudo apt install ./hailo-tappas-core_5.3.0_arm64.deb
```

**UNCERTAIN:** Exact long-term URL layout and Pi OS packaging (`h10-hailort` vs generic `hailort` naming) drift; GenAI `.deb` dependency naming has bitten people (`hailort` vs `h10-hailort`). Prefer Pi `hailo-h10-all` on Trixie when possible; use Developer Zone / `dev-public` when you need 5.3.x.

Developer Zone (login): https://hailo.ai/developer-zone/  
HailoRT docs (login for full set): https://hailo.ai/developer-zone/documentation/hailort/latest/  
HailoRT v5.3.0 guide: https://hailo.ai/developer-zone/documentation/hailort-v5-3-0/

### 2.5 Driver naming gotcha (10H)

**FACT (community + kernel logs):** Hailo-10H probes with **`hailo1x_pci`**, not the legacy **`hailo_pci`** module used for Hailo-8. If both are present, `hailo_pci` can win the probe and `hailortcli` returns nothing despite `lspci` seeing `1e60:45c4`.

Thread: https://community.hailo.ai/t/hailo-10h-fails-to-initialize-on-clean-raspberry-pi-os-install-due-to-legacy-hailo-pci-driver-conflict/18986

Mitigation discussed there (if needed): blacklist `hailo_pci`, or remove stale in-tree/DKMS modules and keep only the H10 driver ≥ 5.0.

---

## 3. Vision demos that officially run with Pi + Hailo (incl. HAT+ 2)

Pi docs state vision instructions apply to AI Kit, AI HAT+, **and AI HAT+ 2**:

```bash
sudo apt update && sudo apt install rpicam-apps
rpicam-hello   # sanity

# Object detection
rpicam-hello -t 0 --post-process-file /usr/share/rpi-camera-assets/hailo_yolov6_inference.json
rpicam-hello -t 0 --post-process-file /usr/share/rpi-camera-assets/hailo_yolov8_inference.json
rpicam-hello -t 0 --post-process-file /usr/share/rpi-camera-assets/hailo_yolox_inference.json
rpicam-hello -t 0 --post-process-file /usr/share/rpi-camera-assets/hailo_yolov5_inference.json

# Instance / object segmentation
rpicam-hello -t 0 --post-process-file /usr/share/rpi-camera-assets/hailo_yolov5_segmentation.json --framerate 20

# Pose (17-point)
rpicam-hello -t 0 --post-process-file /usr/share/rpi-camera-assets/hailo_yolov8_pose.json
```

**UNCERTAIN for our USB cam:** Stock demos assume Raspberry Pi Camera Module + libcamera. MasterPi uses a USB camera (`/dev/video0`); may need Hailo-apps / OpenCV / GStreamer paths instead of `rpicam-*`.

---

## 4. Official model zoo & apps that target Hailo-10H specifically

### 4.1 Vision Model Zoo (HEF compile/eval)

- Repo: https://github.com/hailo-ai/hailo_model_zoo  
- **FACT:** `master` = **Hailo-10 / Hailo-15**; Hailo-8 / 8L live on **v2.x** + Dataflow Compiler **v3.x**.  
- Default compile target on master is **Hailo-10H** (`hailomz compile <model>`; `--hw-arch hailo15h` etc. for others).  
- Public model tables for 10H:  
  https://github.com/hailo-ai/hailo_model_zoo/tree/master/docs/public_models/HAILO10H  

Observed **HAILO10H** task docs (filenames = tasks):

| Task family | RST / support |
|-------------|----------------|
| Object detection | `HAILO10H_object_detection.rst` (YOLO v5–v12, YOLOX, DETR, NanoDet, …) |
| Instance / semantic segmentation | `HAILO10H_instance_segmentation.rst`, `HAILO10H_semantic_segmentation.rst` |
| Pose | `HAILO10H_pose_estimation.rst`, `HAILO10H_single_person_pose_estimation.rst` |
| Depth | `HAILO10H_depth_estimation.rst`, stereo + zero-shot depth variants |
| CLIP / zero-shot | `HAILO10H_zero_shot_classification.rst` (CLIP / SigLIP / TinyCLIP encoders), plus zero-shot detection/segmentation |
| Face / hand / ReID / OCR / SR / etc. | face_*, hand_landmark, person_re_id, text_*, super_resolution, … |

Model Explorer (filter by Hailo-10H): https://hailo.ai/products/hailo-software/model-explorer-vision/

**FACT:** HEFs are **architecture-specific**. A Hailo-8 HEF is not a drop-in for Hailo-10H; compile / download for `hailo10h`.

### 4.2 Hailo Apps (runtime demos; arch-aware)

- Primary repo: https://github.com/hailo-ai/hailo-apps  
- Install guide: https://github.com/hailo-ai/hailo-apps/blob/main/doc/user_guide/installation.md  
- Supports `--arch hailo8 | hailo8l | hailo10h`; auto-detect when possible.

```bash
git clone https://github.com/hailo-ai/hailo-apps.git
cd hailo-apps
# prerequisites: H10 runtime already installed
sudo ./install.sh
source setup_env.sh

hailo-detect-simple
hailo-pose
hailo-seg
hailo-depth
# CLIP zero-shot (pipeline app)
# GenAI (10H only):
#   hailo-download-resources --group vlm_chat|llm_chat|whisper_chat
#   or --include-gen-ai
```

**FACT:** GenAI app groups `vlm_chat`, `llm_chat`, `whisper_chat` are **Hailo-10H only**.

Supported runtime versions stated by hailo-apps install doc:

- Hailo-8 / 8L: HailoRT **4.23**, TAPPAS Core **5.1.0**  
- Hailo-10H: HailoRT **5.1.1 / 5.2.0 / 5.3.0**, TAPPAS Core **5.1.0 / 5.2.0 / 5.3.0**

### 4.3 GenAI Model Zoo + hailo-ollama (10H / AI HAT+ 2)

Pi docs section “Run LLMs on Raspberry Pi 5 (AI HAT+ 2 only)”:

```bash
# After hailo-h10-all (or equivalent H10 runtime)
sudo dpkg -i hailo_gen_ai_model_zoo_5.1.1_arm64.deb   # version Pi docs cite
hailo-ollama
curl --silent http://localhost:8000/hailo/v1/list
curl --silent http://localhost:8000/api/pull \
  -H 'Content-Type: application/json' \
  -d '{ "model": "qwen2:1.5b", "stream": true }'   # replace with listed tag
```

- GenAI zoo repo: https://github.com/hailo-ai/hailo_model_zoo_genai  
- Deb download often cited: `https://dev-public.hailo.ai/…/Hailo10/hailo_gen_ai_model_zoo_5.1.1_arm64.deb`  
- VLM / other GenAI: follow Hailo apps (`hailo-apps`), not only Pi LLM page.

**FACT (Pi product docs):** AI HAT+ 2 on-board 8 GB RAM enables LLMs/VLMs up to roughly **~6B parameters**; AI HAT+ does not.

**NPU exclusivity (UNCERTAIN / operational):** Community notes that `hailo-ollama` / VLM / Whisper may take exclusive VDevice access — stop other Hailo pipelines when running GenAI.

### 4.4 Older / related example repos

| Repo | Notes |
|------|--------|
| https://github.com/hailo-ai/hailo-rpi5-examples | Linked from Pi AI docs; historically Hailo-8-oriented — **verify arch before relying on HEFs** |
| https://github.com/hailo-ai/Hailo-Application-Code-Examples | Lower-level API samples |
| https://github.com/hailo-ai/hailort | Open-source runtime sources + examples |
| https://github.com/hailo-ai/hailort-drivers | PCIe drivers (use **master / H10**, not hailo8-only branch) |

---

## 5. Hailo-8 / 8L / 10H differences that matter for us

| Dimension | Hailo-8L | Hailo-8 | Hailo-10H (our HAT) |
|-----------|----------|---------|---------------------|
| Pi product | AI Kit / AI HAT+ 13 TOPS | AI HAT+ 26 TOPS | **AI HAT+ 2** |
| Peak TOPS (vendor) | 13 INT8 | 26 INT8 | **40 INT4** (CV marketed ~comparable to 26 TOPS HAT+) |
| On-accelerator DRAM | No (uses Pi RAM) | No | **8 GB on HAT** |
| GenAI (LLM/VLM/Whisper) | No (official Pi) | No | **Yes** |
| Pi apt metapackage | `hailo-all` | `hailo-all` | **`hailo-h10-all`** |
| Runtime generation | HailoRT **4.x** | HailoRT **4.x** | HailoRT **5.x** (`h10-hailort`) |
| Kernel driver family | `hailo_pci` | `hailo_pci` | **`hailo1x_pci`** |
| PCI ID (example) | Hailo-8 family `1e60:2864` | `1e60:2864` | **`1e60:45c4`** |
| Model Zoo branch | v2.x + DFC 3.x | v2.x + DFC 3.x | **master + DFC 5.x** |
| HEF portability | 8L HEFs may run on 8 (not reverse) | — | **Separate compile** |

**For house-roaming + pickup:**  
- **Detection / pose / seg / depth / CLIP** exist on all three arches in hailo-apps, but **must use hailo10h HEFs**.  
- **10H extras that help robotics narrative:** on-HAT memory, stronger transformer/CLIP class models, optional VLM for “what is that object?” — at the cost of exclusive NPU use and heavier SW.

---

## 6. Supported tasks (10H) — concrete map

| Task | Official path | Robot relevance |
|------|---------------|-----------------|
| Object detection | Model Zoo HAILO10H + `hailo-detect*` + rpicam YOLO JSONs | **Primary** for “what/where is the object” |
| Instance / semantic segmentation | MZ + `hailo-seg` + rpicam seg JSON | Grasp mask / table segmentation |
| Pose estimation | MZ (`yolov8*_pose`) + `hailo-pose` + rpicam pose JSON | Person avoidance; less critical for object pickup |
| Monocular depth | MZ depth + `hailo-depth` (scdepthv3 in apps) | Approach distance — **relative**, not necessarily metric |
| CLIP / zero-shot classify | MZ CLIP encoders + hailo-apps CLIP pipeline | Open-vocab “find the mug” without retraining |
| Zero-shot detection / seg | MZ HAILO10H zero-shot_* docs | Speculative win for cluttered homes |
| Face / hand / ReID / OCR | MZ HAILO10H tables | Secondary |
| LLM | GenAI zoo + `hailo-ollama` | Planning / voice — **not** closed-loop control |
| VLM | hailo-apps `vlm_chat` (10H only) | Scene QA for recovery behaviors |
| Whisper ASR | hailo-apps `whisper_chat` (10H only) | Voice commands |

**Depth caveat (FACT from hailo-apps depth README):** scdepthv3 outputs may be **relative / normalized**, not true meters — fine for “closer/farther”, risky as sole grasp-range sensor.

---

## 7. Link index (official-ish)

### Raspberry Pi

- AI software: https://www.raspberrypi.com/documentation/computers/ai.html  
- AI HATs hardware: https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html  
- AI HAT+ 2 announcement: https://www.raspberrypi.com/news/introducing-the-raspberry-pi-ai-hat-plus-2-generative-ai-on-raspberry-pi-5/  
- Product brief PDF: https://pip-assets.raspberrypi.com/categories/1319-raspberry-pi-ai-hat-2/documents/RP-009655-MM-4-raspberry-pi-ai-hat-plus-2-product-brief.pdf  

### Hailo docs / downloads

- Developer Zone: https://hailo.ai/developer-zone/  
- HailoRT latest docs: https://hailo.ai/developer-zone/documentation/hailort/latest/  
- Software suite overview: https://hailo.ai/products/hailo-software/hailo-ai-software-suite/  
- Vision Model Explorer: https://hailo.ai/products/hailo-software/model-explorer-vision/  
- Terms of use (EULA-style restrictions): https://hailo.ai/terms-of-use/  
- Community forum: https://community.hailo.ai/  
- Public debs (example root): https://dev-public.hailo.ai/  

### GitHub `hailo-ai` (high signal)

- https://github.com/hailo-ai/hailo_model_zoo  
- https://github.com/hailo-ai/hailo_model_zoo_genai  
- https://github.com/hailo-ai/hailo-apps  
- https://github.com/hailo-ai/hailort  
- https://github.com/hailo-ai/hailort-drivers  
- https://github.com/hailo-ai/hailo-rpi5-examples  
- https://github.com/hailo-ai/Hailo-Application-Code-Examples  

Note: full HTML docs live primarily under **Developer Zone**, not a public `docs.hailo.ai` site that indexes without login. Prefer the URLs above.

---

## 8. License / redistribution constraints (HEF & stack)

| Artifact | License posture | Practical constraint |
|----------|-----------------|----------------------|
| `hailo_model_zoo` **code** | **MIT** (repo LICENSE) | Free to use/modify/redistribute code |
| Pretrained ONNX/TF weights | Often **upstream** model license (check each `license_url` / source) | Separate from Hailo |
| Compiled **HEF** binaries | Distributed via Hailo Zoo / apps tooling; **not** clearly MIT | Treat as **Hailo proprietary binaries** for use **with Hailo hardware**; do not assume public redistributable rights without checking the download terms / Developer Zone EULA |
| HailoRT / firmware / PCIe driver | Proprietary EULA | Binary redistrib allowed **only** with Hailo products / End-User Products; no reverse engineering; **no public benchmarking** disclosure in FW license text |
| Hailo-10H FW license (in hailort-drivers) | https://github.com/hailo-ai/hailort-drivers/blob/master/Hailo10H%20FW%20License | Explicit binary-only redistrib with purchased Hailo Products |

**Recommendation for this repo:** keep HEFs under local ignored paths (already noted in `docs/hailo.md`); document download commands; do **not** commit large HEF dumps or GenAI weights to git.

---

## 9. Implications for tiny_pi_car (facts vs speculation)

### Facts

1. We have a real **Hailo-10H** (`1e60:45c4`); software stack is still missing (**LOCAL**).  
2. Official Pi install for this HAT is **`hailo-h10-all`**, currently published for **Trixie**, not present on **this Bookworm** apt.  
3. Installing Bookworm `hailo-all` 4.20 is the **wrong** product line.  
4. Vision tasks we need (detect / seg / pose / depth / CLIP) have **official hailo10h** Model Zoo + hailo-apps coverage.  
5. GenAI is a **10H differentiator** but competes for the NPU with vision pipelines.

### Speculation (robot roadmap — not claims)

- **Pickup stack:** YOLOv8n/s or YOLO11n (`hailo10h` HEF) → optional seg mask → depth prior → arm IK. Start with detect-only.  
- **Open-vocab fetch:** CLIP / zero-shot detection on 10H could reduce per-object retraining for “household junk.”  
- **VLM fallback:** when detector fails, brief VLM query — only if vision pipeline can release the device.  
- **OS decision:** migrating this Pi to **Trixie** is likely the lowest-friction path to official packages; staying on Bookworm means living on Hailo `dev-public` / Developer Zone debs and sharper edges.

### Immediate next actions (concrete)

1. Choose **Trixie + `hailo-h10-all`** *or* Bookworm + Hailo 5.x debs from Developer Zone / `dev-public`.  
2. Verify: `hailortcli fw-control identify` shows `Device Architecture: HAILO10H`.  
3. Confirm driver: `lsmod | grep hailo` → prefer `hailo1x_pci`; ensure legacy `hailo_pci` is not blocking.  
4. Run `hailo-detect-simple` (or rpicam demos if using CSI cam).  
5. Download **hailo10h** detection HEF only; keep models out of git.  
6. ~~Update `docs/hailo.md` so it no longer recommends 4.20 `hailo-all`~~ **DONE** — hailo.md documents Path B / forbids Bookworm `hailo-all`.

---

## 10. Uncertainty register

| Item | Status |
|------|--------|
| Bookworm support for `hailo-h10-all` | **Absent in apt today (LOCAL)**; Pi docs emphasize Trixie |
| Whether rpicam Hailo JSON demos work with MasterPi USB cam | **Uncertain** — likely need hailo-apps / V4L2 |
| Exact GenAI model list / tags at 5.1.1 vs 5.3.0 | Drift reported in community; query `/hailo/v1/list` after install |
| Metric accuracy of stock depth HEFs for grasp distance | Likely **relative**; treat as assist, not ground truth |
| Coexistence of vision + LLM on one 10H without time-slicing | Assume **exclusive** until proven otherwise |
| HEF redistribution for shipping a product image | Read current Developer Zone EULA before bundling |

---

*End of research note.*
