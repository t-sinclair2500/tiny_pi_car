# Start motion-hour run (host)

Wheels are **allowed for this ~1 hour window only** — see
[`MOTION_HOUR_CARD.md`](./MOTION_HOUR_CARD.md) for the fence (vision-nav primary).
After the window ends, go back to perception-only (`NIGHT_CARD.md`) unless a human
says otherwise.

## Model map (this hour)

| Role | Model | Notes |
|---|---|---|
| **Lead / manager** | `lm-studio/qwen3.6-35b-a3b-mtp` | Plans, decides trials, reviews — not every bash/snap |
| **Worker / medium** | `lm-studio/qwen3.5-9b-mtp` | Execution: edits, SSH, snaps, Hailo, motion |
| **Helper / quick** | `lm-studio/qwen3.5-2b` | Greps, status, tiny checks (must use as subagent) |
| **Reviewer** | `lm-studio/qwen3.5-9b-mtp` | Occasional keep/reject only |
| **pi-observer / pi-motion** | `lm-studio/qwen3.5-9b-mtp` | Medium Pi tasks |
| ~~27B~~ | **unused / unloaded** | Never on the hot path |

Standing order: **manage on 35B; MUST call 1–2 concurrent subagents (2B and/or 9B)** for grunt work.

## Bring-up

```bash
cd ~/Documents/GitHub/tiny_pi_car
systemctl --user start lms-openai-proxy   # :1240 → LM Studio :1234
systemctl --user restart opencode-serve   # restart AFTER the proxy so it picks up baseURL
```

Smoke (expect a short reply in a few seconds):

```bash
SES=$(curl -sS -X POST "http://127.0.0.1:4096/session?directory=$(pwd)" -d '{"title":"smoke"}')
SESSION_ID=$(echo "$SES" | python3 -c "import json,sys;print(json.load(sys.stdin)['id'])")
curl -sS -X POST "http://127.0.0.1:4096/session/${SESSION_ID}/message?directory=$(pwd)" \
  -H 'Content-Type: application/json' \
  -d '{"model":{"providerID":"lm-studio","modelID":"qwen3.5-9b-mtp"},"agent":"quick",
       "parts":[{"type":"text","text":"Reply with one short sentence confirming you are online."}]}'
```

## Start the council loop (isolated worktree)

```bash
.venv/bin/python scripts/start_autoresearch_worktree.py \
  --tag motion-hour-2 -- \
  --campaign autoresearch/car/campaigns/motion-hour.toml \
  --council --director-every 2 --iterations 8 --agent-timeout 240 --plateau-limit 8 \
  --director-model lm-studio/qwen3.6-35b-a3b-mtp \
  --worker-model lm-studio/qwen3.5-9b-mtp \
  --helper-model lm-studio/qwen3.5-2b \
  --reviewer-model lm-studio/qwen3.5-9b-mtp \
  --attach http://127.0.0.1:4096
```

Or relaunch inside existing worktree `motion-hour-1` after syncing files:

```bash
cd /tmp/tiny_pi_car-autoresearch/motion-hour-1
# emergency-stop first (see below), then:
nohup .venv/bin/python scripts/autoresearch_loop.py \
  --campaign autoresearch/car/campaigns/motion-hour.toml \
  --council --director-every 2 --iterations 8 --agent-timeout 240 --plateau-limit 8 \
  --director-model lm-studio/qwen3.6-35b-a3b-mtp \
  --worker-model lm-studio/qwen3.5-9b-mtp \
  --helper-model lm-studio/qwen3.5-2b \
  --reviewer-model lm-studio/qwen3.5-9b-mtp \
  --attach http://127.0.0.1:4096 \
  > /tmp/motion-hour-loop.log 2>&1 &
echo "loop_pid=$!"
```

Logs: `<worktree>/.autoresearch/runs/motion-hour-<timestamp>/`.

### Paste prompt (OpenCode / director)

```text
Read autoresearch/car/MOTION_HOUR_CARD.md and autoresearch/car/program.md.
You are the LEAD/MANAGER on qwen3.6-35b-a3b-mtp: plan, decide trials, review results.
Do NOT grind every bash/grep/snap yourself. When managing the loop, MUST call
1–2 concurrent subagents: helper=qwen3.5-2b for quick checks; worker/pi-observer/
reviewer-style=qwen3.5-9b-mtp for medium execution. Prefer spawning them.
27B is unused — never route to it.
Wheels allowed this hour only. Camera starts neutral/cam-up (ArmIK 0,6,18);
re-snap if unsure (see /tmp/tiny_pi_car/snap-after-arm-reset.jpg).
PRIMARY: vision-nav — snap/perceive → one short safe move → stop → resnap.
Dispatch overhead is secondary. Always --allow-wheels; prefer --with-vision.
Log under .autoresearch/runs/.
```

## How to watch

- OpenCode TUI: `opencode --attach http://127.0.0.1:4096`
- Tail `/tmp/motion-hour-loop.log`
- Tail results: `column -t -s $'\t' <run_dir>/results.tsv`

## How to kill

```bash
pgrep -af scripts/autoresearch_loop.py
kill <loop_pid>
pkill -f "opencode run" || true
```

## STOP MOTORS (emergency)

```bash
.venv/bin/python scripts/pi_agent_gate.py emergency-stop \
  --host rpicarbox.local --remote-root /home/tyler/Desktop/tiny_pi_car
```

## End of window

```bash
.venv/bin/python scripts/pi_agent_gate.py emergency-stop \
  --host rpicarbox.local --remote-root /home/tyler/Desktop/tiny_pi_car
.venv/bin/python scripts/pi_agent_gate.py status --host rpicarbox.local
```

Go back to `NIGHT_CARD.md` / perception-only for further unattended runs.
