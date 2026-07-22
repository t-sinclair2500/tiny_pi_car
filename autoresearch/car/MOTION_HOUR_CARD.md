# Motion-hour card — wheels ALLOWED, ~60 min, untethered

**Audience / model map (this hour):**
- **Lead / manager:** `autoresearch-director` on **qwen3.6-35b-a3b-mtp** — plans, decides trials, reviews results. Does **not** grind every bash/grep/snap.
- **Must use subagents (1–2 concurrent):** **2B** helper for quick checks; **9B** worker / pi-observer / reviewer for medium execution (snaps, Hailo, motion, edits).
- **27B:** unloaded / **not used**.
**Host SSH:** `rpicarbox.local` (alias `rpicarbox-1`). Repo on Pi: `/home/tyler/Desktop/tiny_pi_car`.
**Window:** roughly one hour, untethered, full motion permitted. **This overrides the
`NIGHT_CARD.md` "no wheel motion" default for this session only** — after the window
ends, go back to perception-only unless a human says otherwise.

## Camera pose (this hour)

- Camera starts **neutral / cam-up**: ArmIK `(0, 6, 18)` — looking forward/level.
- Reference snap on Pi: `/tmp/tiny_pi_car/snap-after-arm-reset.jpg`.
- If another agent may have moved the arm/camera, **re-snap before trusting vision**
  (`pi_agent_gate.py camera-snap` or `playground.camera_snap`). Do not assume the
  last frame is still forward-looking.
- No stock MasterPi services required; stop `masterpi.service` only if it is active
  and blocking UART/camera.

## Hard fence (this hour)

| Allowed | Forbidden |
|---|---|
| Short, timed `forward` / `reverse` / `yaw_left` / `yaw_right` trials via `physical_trial` / `pi_agent_gate.py motion-trial`, **always** with `--allow-wheels` passed explicitly | Any wheel/mecanum command without `--allow-wheels` |
| Low speed (`--speed-mm-s` ≤ 60), short duration (`--duration-s` ≤ 2.0 for exploration, ≤ 0.8 for the scored metric) | High speed, long duration, or chained moves with no stop between them |
| Sonar-gated forward moves (default `respect_sonar=True`); disable sonar (`--no-sonar`) only on a rotate-in-place trial with a human present | `--no-sonar` on `forward`/`reverse`, or driving toward an unmeasured obstacle |
| **Vision-conditioned trials:** snap → Hailo perceive → choose one small move → stop → resnap | Driving without a stop between moves; treating captures as a substitute for `final_stop_sent` |
| Editing `playground/autoresearch/**`, `playground/autonomy/**`, `autoresearch/car/**`, `scripts/motion_hour_eval.py`, `scripts/pi_agent_gate.py` | Unbounded loops (`while True` drive), disabling the `stop_all()` / `trap cleanup EXIT` pattern, removing hard gates from the evaluator to "win" |
| Arm/gripper moves **only if** timed + stopped and not required for this hour's goal | Leaving motors running in a background job; ending a trial without an explicit stop |

Always: stop `masterpi.service` before owning the UART/wheels. Every trial must end in
`stop_all()` (see `physical_trial.run_trial`'s `finally` block) — that is non-negotiable
even when a trial errors out.

## Why this is safe

- `pi_agent_gate.py` and `playground/autoresearch/physical_trial.py` both refuse chassis
  actions (`forward`/`reverse`/`yaw_left`/`yaw_right`) unless `--allow-wheels` is passed
  (or `TINY_PI_ALLOW_WHEELS=1`). Nothing in this packet weakens that fence — it documents
  *when* to pass it, not a way around it.
- `physical_trial.py` hard-caps duration (≤ 8.0 s), speed (≤ 120 mm/s), and yaw (≤ 1.0),
  and always calls `robot.stop_all()` in a `finally` block, sonar-gated by default.
- The scored metric never rewards more speed, more duration, or more distance — only a
  *clean, fully-stopped* trial plus an optional honest vision step. See "Council metric".

## Goals for this hour (primary = vision-nav)

1. **Primary:** short **vision-conditioned** motion trials — snap/perceive (camera + Hailo)
   → choose one small safe move → explicit stop → resnap. Improve the perceive→decide→
   move loop under the hard fence.
2. Get at least one honest, fully-stopped chassis trial logged with vision evidence
   (snap and/or Hailo dets) in the same trial cycle.
3. **Secondary:** reduce **dispatch overhead** (SSH + process + startup latency) without
   touching safety caps — useful, but not the main hypothesis family this hour.
4. Confirm sonar-gated `forward`/`reverse` clearance veto still fires (staged, low speed)
   when you leave rotate-in-place.

## Hypotheses to try in ~60 min (pick ONE per trial; cycle families on plateau)

**Vision-nav (prefer these):**

1. **Snap → decide → yaw** — one forward snap + Hailo dets; if free space / no blocking
   det in center, `yaw_left`/`yaw_right` 0.4–0.6 s @ ≤40 mm/s; stop; resnap.
2. **Snap → short forward** — only if sonar clear and vision does not show a near obstacle
   in the lower/center FOV; `--duration-s` ≤ 0.5, `--speed-mm-s` ≤ 40.
3. **Perception latency on the move path** — keep Hailo warm (VDevice / short
   `log_detections`) so perceive→move gap shrinks without weakening gates.
4. **Camera ownership** — if snap fails or FOV looks wrong, re-assert cam-up / re-snap
   before scoring; do not drive on a stale or sideways frame.
5. **HEF A/B for nav usefulness** — swap Hailo-10H HEFs only if dets/latency clearly
   help choose the next short move (not night-style perception-only chasing).

**Dispatch (secondary):**

6. SSH `ControlMaster` / fewer cold Python imports / skip redundant `systemctl stop`
   when already inactive — measure `dispatch_overhead_ms` as a side metric.

## Council metric (fixed scalar — maximize)

| Field | Role |
|---|---|
| **`score`** | `100 * completion_ratio * overhead_factor * vision_factor` (see `scripts/motion_hour_eval.py`) |
| `completion_ratio` | `executed_steps / expected_steps`, 0..1 |
| `overhead_factor` | rewards *less* SSH/process latency (secondary) |
| `vision_factor` | with `--with-vision`: 1.0 if post-stop snap+Hailo step ok, else 0.5; without flag: 1.0 |
| **`hard_gates_passed`** | `final_stop_sent == true` AND `executed_steps >= 1` AND `stop_reason != "aborted_before_final_stop"` (vision failure does **not** bypass these) |

Host command (vision-nav primary eval):

```bash
.venv/bin/python scripts/motion_hour_eval.py \
  --host rpicarbox.local --remote-root /home/tyler/Desktop/tiny_pi_car \
  --action yaw_left --duration-s 0.6 --speed-mm-s 40 --yaw 0.3 \
  --allow-wheels --with-vision --json
```

Dispatch-only (secondary / debug):

```bash
.venv/bin/python scripts/motion_hour_eval.py \
  --host rpicarbox.local --remote-root /home/tyler/Desktop/tiny_pi_car \
  --action yaw_left --duration-s 0.6 --speed-mm-s 40 --yaw 0.3 \
  --allow-wheels --json
```

Log under `.autoresearch/runs/`.

## Success metrics (this hour)

- At least one real, logged, fully-stopped chassis trial with `hard_gates_passed: true`
  **and** a vision step (snap and/or Hailo) in the same cycle.
- Hypotheses primarily about perceive→decide→short-move, not SSH ceremony alone.
- Zero incidents of `final_stop_sent: false` or `aborted_before_final_stop` left unlogged.
- No wheel command ever issued without `--allow-wheels` visible in the command/log.

## Director standing order (this hour)

1. **Manage on 35B; execute via 9B/2B.** When running the loop you **MUST call 1–2
   subagents** (max concurrent): helper=2B for quick checks; worker / pi-observer /
   reviewer-style=9B for snaps, Hailo, motion, medium edits. Prefer spawning them over
   doing grunt work on 35B. **27B is unused.**
2. Run ONE baseline motion-hour trial with `--with-vision` before proposing changes.
3. One change per trial; keep/discard with numbers.
4. Prefer vision-nav hypotheses; use rotate-in-place while iterating; save forward for
   staged sonar+vision checks.
5. You may edit this file, `program.md`, and `campaigns/motion-hour.toml` if the fence
   stays: **`--allow-wheels` explicit, low speed, short duration, explicit stop**.
6. Reviewer (9B) blocks only: fake metrics, wheel motion without `--allow-wheels`,
   unbounded loops, missing/altered final stop, weakening hard gates. Occasional —
   not every brainstorm.
7. **When the hour is up (or the human returns), stop proposing new motion trials** and
   hand back to `NIGHT_CARD.md` / perception-only work.

## Start (human / host)

```bash
lms server status   # 35B + 9B + 2B; do NOT load 27B for this hour
systemctl --user start lms-openai-proxy   # :1240 → LM Studio :1234
opencode serve --port 4096
# then see autoresearch/car/START_MOTION_HOUR.md
```
