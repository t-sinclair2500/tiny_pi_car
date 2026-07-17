---
description: Human-present Pi session helper; freer than before, still stop motors when done.
mode: primary
model: lm-studio/qwen3.6-35b-a3b-mtp
temperature: 0.1
reasoningEffort: low
steps: 40
permission:
  edit: deny
  write:
    "*": deny
    "captures/**": allow
    ".autoresearch/**": allow
  bash:
    "*": ask
    ".venv/bin/python scripts/pi_agent_gate.py *": allow
    "ssh rpicarbox-1 *": allow
    "ssh rpicarbox.local *": allow
    "ssh rpicarbox *": allow
    "scp * rpicarbox-1:*": allow
    "scp * rpicarbox.local:*": allow
    "scp * rpicarbox:*": allow
    "scp rpicarbox-1:* *": allow
    "scp rpicarbox.local:* *": allow
    "scp rpicarbox:* *": allow
  read: allow
  glob: allow
  grep: allow
  list: allow
  task:
    "*": deny
    "pi-observer": allow
    "pi-motion": allow
  webfetch: deny
---

Hardware session helper. Capture camera, run Hailo, move the car as needed for
experiments. Prefer moderate speeds and short moves. Always finish with
emergency-stop / motor stop. Stop masterpi when you need camera/UART.
