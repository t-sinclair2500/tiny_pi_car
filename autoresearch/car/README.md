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
# Strip LM Studio empty tool_calls: [] so OpenCode does not hang on them
python3 scripts/lms_openai_proxy.py   # :1240 → LMS :1234
# or: systemctl --user start lms-openai-proxy
# ~/.config/opencode/opencode.jsonc lm-studio baseURL → http://127.0.0.1:1240/v1
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
systemctl --user restart opencode-serve   # picks up baseURL
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

Perception-only default: [`NIGHT_CARD.md`](./NIGHT_CARD.md) · [`START_NIGHT.md`](./START_NIGHT.md).
Motion-hour window (wheels ALLOWED, ~60 min, human present):
[`MOTION_HOUR_CARD.md`](./MOTION_HOUR_CARD.md) · [`START_MOTION_HOUR.md`](./START_MOTION_HOUR.md) ·
campaign [`campaigns/motion-hour.toml`](./campaigns/motion-hour.toml).
Stream roam (continuous on-Pi loop, no OpenCode):
[`STREAM_CARD.md`](./STREAM_CARD.md) · [`START_STREAM.md`](./START_STREAM.md) ·
campaign [`campaigns/stream-roam.toml`](./campaigns/stream-roam.toml).

Hard rules are few: **no wheels unless a motion-hour or stream card is explicitly active**,
and even then only via `--allow-wheels`, no secrets, hailo10h HEFs only, timed stops with an
explicit final stop, prefer `playground/`.

## Experiment digest

Committed write-up of scores, laundry-jam failure, and stream leapfrog status:
[`docs/autonomy/EXPERIMENT_LEARNINGS.md`](../../docs/autonomy/EXPERIMENT_LEARNINGS.md).
Raw tick JSON stays under `.autoresearch/runs/` (gitignored).
