# OpenCode autonomy autoresearch

Local Qwen models via OpenCode + SSH to the Pi (Hailo-10H + HiWonder), iterating
toward useful car autonomy. Agents may revise `program.md`, campaigns, and plans.

## Roles / models

| Role | Model | Job |
|---|---|---|
| Director | `qwen3.6-27b-mtp` | Propose experiments, revise directives, spawn worker |
| Worker | `qwen3.6-35b-a3b-mtp` | Edit playground, run camera/Hailo/motion trials |
| Helper | `qwen3.5-2b` | Quick pytest/ruff/greps |
| Reviewer | `qwen3.5-9b-mtp` | Block only clear cheating / fake results / unbounded motion |

Agents can use vision (snap frames and **read the images**), A/B Hailo-10H zoo
HEFs, and drive the robot for experiments. Always stop motors when a trial ends.

## Bring-up

```bash
lms server status
opencode models lm-studio

# optional loads
lms load qwen3.6-27b-mtp --estimate-only
lms load qwen3.6-35b-a3b-mtp --estimate-only
lms load qwen3.5-9b-mtp --estimate-only
lms load qwen3.5-2b --estimate-only

# offline smoke (expect hard_gates_passed + score ~85 on current baseline)
.venv/bin/python scripts/autoresearch_loop.py --baseline-only
.venv/bin/python -m playground.autoresearch.evaluate --json

# council run (director every N trials)
opencode serve --port 4096
.venv/bin/python scripts/start_autoresearch_worktree.py \
  --tag autonomy-1 -- \
  --council --director-every 3 --iterations 12 \
  --attach http://127.0.0.1:4096
```

Or just open OpenCode and talk to `autoresearch-director` / `autoresearch-worker`.

## Useful helpers

```bash
# Pi status / camera / motion
.venv/bin/python scripts/pi_agent_gate.py status
.venv/bin/python scripts/pi_agent_gate.py camera-snap --stop-masterpi
.venv/bin/python scripts/pi_agent_gate.py perception --frames 30 --stop-masterpi
.venv/bin/python scripts/pi_agent_gate.py motion-trial --duration-s 1.0 --speed-mm-s 40

# Hailo A/B on a folder of frames
.venv/bin/python scripts/hailo_ab_compare.py \
  --hef-a playground/vision/models/yolov8n.hef \
  --hef-b .autoresearch/artifacts/yolov8s.hef \
  --images captures/ab_frames
```

Copy snapped frames back with `scp` and inspect them in the IDE (Read tool on jpg).

Vision suite (zoo A/B + custom HEF slots): `playground/vision/suite/` ·
`scripts/vision_suite_status.py --host rpicarbox.local`

Pi live facts (Trixie bring-up): [`docs/autonomy/PI_BRINGUP.md`](../../docs/autonomy/PI_BRINGUP.md).

## Contract

See [`NIGHT_CARD.md`](./NIGHT_CARD.md) · [`START_NIGHT.md`](./START_NIGHT.md). Hard rules are few: **no wheels tonight**,
no secrets, hailo10h HEFs only, timed stops, prefer `playground/`.
