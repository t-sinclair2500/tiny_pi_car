# Autonomy research program

Open-world Autoresearch for this MasterPi car: local Qwen models via OpenCode,
SSH to the Pi (Hailo-10H + HiWonder), iterate until the car is more autonomous.

The director (27B), worker (35B), helper (2B), and reviewer (9B) may revise this
file, campaign TOMLs, plans, and schedules when that improves progress.

**Tonight:** follow [`NIGHT_CARD.md`](./NIGHT_CARD.md). **No wheel / chassis motion.**

## Goal

Useful autonomy: perceive the scene, choose an action, move/grasp safely enough
to complete household-scale tasks. Prefer measured gains over ceremony.

Tonight’s slice: **maximize useful perception** (camera lane speed, Hailo throughput,
Pi↔Hailo split) without driving.

## Loop

1. Hypothesize one change (code, HEF, threshold, pipeline, …).
2. Implement it (worker edits `playground/` freely).
3. Measure with the cheapest honest check (live camera + Hailo latency/dets,
   image inspection, A/B HEFs). No chassis trials tonight.
4. Keep if perception got better; otherwise discard and log why.
5. Repeat. After a plateau, change the hypothesis family — do not weaken truth.

## Freedom (intentional)

- Agents may use camera frames and **look at images** themselves.
- Agents may A/B Hailo-10H HEFs (fetch, deploy, score, keep winner).
- Agents may stop/start `masterpi.service` when they need the camera.
- Agents may edit directives, campaigns, and schedules under `autoresearch/car/`.
- Arm/gripper only if UART is present and every move is timed + stopped; prefer
  perception-only trials tonight.

## Hard constraints

- **No mecanum / wheel / chassis motion** (see NIGHT_CARD).
- Do not commit secrets (`.env`, Wi‑Fi passwords, keys).
- Hailo artifacts must target `hailo10h` (not Hailo-8 HEFs).
- No unbounded motion loops; every move has a timeout and an explicit stop.
- Prefer `playground/` over rewriting all of `MasterPi/` in one pass.
- Do not invent hardware results; timeouts are failures.
- Device node may be `/dev/hailo0` or `/dev/h1x-0` — probe both.

## Suggested tracks (tonight)

Camera AE/warmup, persistent capture, preprocess cost, score_thresh, HEF A/B
(v8m vs v11m on disk), VDevice keep-alive, async grab∥infer, tracker without motors.
Queue: `NIGHT_CARD.md`.
