# Completion audit — car autonomy autoresearch

Living checklist after simplifying the OpenCode harness.

| Goal | Status | Notes |
|---|---|---|
| Director 27B / Worker 35B / Helper 2B / Reviewer 9B | Configured | `.opencode/agents/*` |
| Agents may edit playground + revise `program.md` / campaigns | Done | Broader editable_paths |
| Camera snap + image inspection | Done | `pi_agent_gate camera-snap`, `playground/camera_snap.py` |
| Free-ish motion (no required arm lease) | Done | Optional arm; always stop on exit |
| Hailo-10H HEF A/B | Scaffolded | `scripts/hailo_ab_compare.py` + model slots |
| Perception eval without mandatory bwrap | Done | `--no-sandbox` / auto-fallback |
| Offline policy arena (handoff stop) | Baseline ~85.5 | `candidate.py` reaches handoff ≤315 mm |
| Vision suite slots + install helpers | Scaffolded | `playground/vision/suite/`, `vision_suite_*.py` |
| Pi SSH defaults (`rpicarbox.local`) | Done | Alias `rpicarbox-1` → `.local` |
| Live Pi overnight council run | Blocked | Waiting on `hailo-h10-all` + venv + HEF |
| Real held-out perception dataset | Missing | Set `TINY_PI_PERCEPTION_GT` when available |

Next: after `/dev/h1x-0` exists, drop `yolov8n.hef` and run `pi_agent_gate hailo-probe` + `log_detections`.
See `docs/autonomy/PI_BRINGUP.md`.
