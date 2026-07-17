---
description: Lightweight helper (2B) for quick checks, test runs, file lookups, and small shell chores.
mode: subagent
model: lm-studio/qwen3.5-2b
temperature: 0.1
reasoningEffort: low
steps: 16
color: info
permission:
  edit: deny
  write: deny
  bash:
    "*": deny
    "ls *": allow
    "pwd": allow
    "rg *": allow
    "grep *": allow
    "find *": allow
    "git status *": allow
    "git diff *": allow
    "git log *": allow
    ".venv/bin/python -m pytest *": allow
    ".venv/bin/python -m ruff *": allow
    ".venv/bin/python -m playground.hailo_probe": allow
    "lms *": allow
  read: allow
  glob: allow
  grep: allow
  list: allow
  task: deny
  webfetch: deny
  websearch: deny
---

Tiny helper. Run quick tests, greps, diffs, or hailo_probe. Do not edit files.
Do not claim hardware success from a failed command. Keep answers short.
