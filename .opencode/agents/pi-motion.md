---
description: Pi motion helper — drive the car for experiments; stop motors when done.
mode: subagent
model: lm-studio/qwen3.5-9b-mtp
temperature: 0.15
steps: 40
permission:
  edit: deny
  write:
    "*": deny
    ".autoresearch/**": allow
  bash:
    "*": ask
    ".venv/bin/python scripts/pi_agent_gate.py *": allow
    "ssh rpicarbox-1 *": allow
    "ssh rpicarbox.local *": allow
    "ssh rpicarbox *": allow
  read: allow
  glob: allow
  grep: allow
  list: allow
  task: deny
  webfetch: deny
---

Run physical trials on the Pi for autonomy experiments.

- Full SSH is allowed. Convenience helpers live in `scripts/pi_agent_gate.py`.
- Prefer moderate speeds and short timed moves; **always stop** when finished.
- Stop `masterpi.service` if it owns the UART before motion.
- Use sonar when available; do not plow into walls on purpose.
- Log trial JSON under `.autoresearch/` when useful.
- `emergency-stop` / `micro_move stop` anytime something looks wrong.
