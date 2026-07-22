# STREAM_CARD — continuous on-Pi roam

Human-present stream research. **Wheels ALLOWED** only with `--allow-wheels`.
Control loop runs **on the Pi** under `/home/tyler/Desktop/tiny_pi_car`.
Host syncs code, starts/stops the daemon, and scores logs. **No OpenCode.**

Prior art: `.autoresearch/runs/motion15-direct/SUMMARY.md`, `.autoresearch/runs/auto20/`.
Committed digest: [`docs/autonomy/EXPERIMENT_LEARNINGS.md`](../../docs/autonomy/EXPERIMENT_LEARNINGS.md).

## Architecture (MVP)

| Rate | Role |
|------|------|
| Sonar ~20–50 Hz | Hard stop if forward clearance breached |
| Vision (latest frame) | Warm Hailo dets → roam FSM |
| Chassis ~10 Hz | FSM → `RobotIO.apply`; dead-man lease |

## States (roam FSM)

`IDLE → SCAN → APPROACH → HOLD | FAULT`

- **SCAN:** no target → hold / small yaw only if floor gate clear
- **APPROACH:** align yaw to bbox; slow forward when centered + sonar clear + no floor clutter
- **HOLD:** stop chassis (grasp hooks later — L4 not live in MVP)
- **FAULT:** stop; log reason

## Hard fence

| Required | Forbidden |
|----------|-----------|
| `--allow-wheels` on every wheeled daemon start | Chassis without flag |
| Max crawl ≤30 mm/s | High speed / unbounded duration |
| Bounded `--duration-s`; always `stop_all` on exit | Motors left running |
| Sonar veto on forward (~220 mm clearance) | `--no-sonar` while crawling |
| Look-down / floor gate before sustained forward when enabled | Yaw-in-place into unknown soft piles |
| Desktop repo only (no stock `masterpi.service`) | OpenCode / LMS proxy in this track |
| Arm pose changes timed + exclusive UART | Drive while arm moving (MVP) |

## Sensing limits (known)

- Ultrasonic sits ~3" off the deck → **misses low floor clutter** (toys, fabric).
- Cam-up FOV is room-level; **look_down** before crawl is the MVP soft-obstacle check.
- Prefer refuse crawl over guessing.

## L3 / L4 unlock (not MVP)

- **L3 sticky track:** after L1/L2 green on clear floor + soft-pile refuse.
- **L4 grasp:** `GraspFSM` only from HOLD; wheels locked; timed gripper. Stub hooks only for now.

## Emergency

```bash
.venv/bin/python scripts/pi_agent_gate.py --host rpicarbox \
  --remote-root /home/tyler/Desktop/tiny_pi_car emergency-stop
```
