# Start Qwen night run (host)

LM Studio is up (`lms` port 1234). Then:

```bash
cd ~/Documents/GitHub/tiny_pi_car
opencode serve --port 4096
```

In OpenCode, open **`autoresearch-director`** and paste:

```text
Read autoresearch/car/NIGHT_CARD.md and autoresearch/car/program.md.
Run perception-only trials tonight: NO wheel/chassis motion
(motion-trial is blocked unless --allow-wheels).
Start with capture_bench + hypothesis 1 (AE/warmup vs capture latency);
baseline infer ~28ms, e2e ~3.5s. Then score_thresh and yolov8m vs yolov11m A/B.
Spawn the worker as needed. Log under .autoresearch/runs/.
```

Optional council loop later:

```bash
.venv/bin/python scripts/start_autoresearch_worktree.py \
  --tag night-perception-1 -- \
  --campaign autoresearch/car/campaigns/perception-latency-night.toml \
  --council --director-every 2 --iterations 20 \
  --attach http://127.0.0.1:4096
```

(Live Pi metrics in NIGHT_CARD beat the stub campaign eval.)
