# Start stream roam (host)

Continuous on-Pi roam — see [`STREAM_CARD.md`](./STREAM_CARD.md). **No OpenCode.**

## Sync + start

```bash
cd ~/Documents/GitHub/tiny_pi_car
HOST=rpicarbox
REMOTE=/home/tyler/Desktop/tiny_pi_car

rsync -az --delete \
  --exclude '.venv' --exclude '.git' --exclude '**/__pycache__' \
  --exclude 'playground/vision/models/*.hef' \
  ./playground ./scripts ./autoresearch \
  "$HOST:$REMOTE/"

# Clear-floor smoke (30s). Human present. Soft piles cleared or use --look-down-first.
.venv/bin/python scripts/pi_agent_gate.py --host "$HOST" --remote-root "$REMOTE" \
  roam-start --duration-s 30 --max-speed-mm-s 25 --allow-wheels --look-down-first

# Watch
.venv/bin/python scripts/pi_agent_gate.py --host "$HOST" --remote-root "$REMOTE" roam-status
ssh "$HOST" 'tail -f /tmp/tiny_pi_car/roam_daemon.jsonl'
```

## Stop

```bash
.venv/bin/python scripts/pi_agent_gate.py --host rpicarbox \
  --remote-root /home/tyler/Desktop/tiny_pi_car roam-stop
# Always:
.venv/bin/python scripts/pi_agent_gate.py --host rpicarbox \
  --remote-root /home/tyler/Desktop/tiny_pi_car emergency-stop
```

## Scored eval (campaign / research)

```bash
.venv/bin/python scripts/stream_roam_eval.py \
  --host rpicarbox \
  --remote-root /home/tyler/Desktop/tiny_pi_car \
  --duration-s 30 --max-speed-mm-s 25 --allow-wheels --look-down-first --json
```

## Composer research SOP (20–30 min)

1. Read `STREAM_CARD.md` + this file.
2. Heartbeats 60–90 s; edit `playground/autonomy/**` / `playground/vision/**` on host.
3. Rsync → `roam-stop` → `roam-start` / re-run `stream_roam_eval.py`.
4. Maximize course `score`; never leave motors running.
5. Do **not** start OpenCode, `opencode serve`, or `lms_openai_proxy`.
