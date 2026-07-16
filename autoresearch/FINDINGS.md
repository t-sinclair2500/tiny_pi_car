# General findings

## What Karpathy built

`karpathy/autoresearch` gives an AI coding agent (Claude Code, Codex, Cursor, etc.) a small but real LLM training setup and lets it experiment autonomously. Typical overnight run: ~12 experiments/hour (~100 while you sleep), each with a fixed **5-minute wall-clock** training budget.

There is **no orchestration daemon**. The agent *is* the automation: you point it at the repo, tell it to follow `program.md`, and leave.

### Three-file contract

| File | Owner | Role |
|------|-------|------|
| `prepare.py` | Immutable | Data, tokenizer, dataloader, `evaluate_bpb`. The "physics" / judge. |
| `train.py` | Agent | GPT model, Muon+AdamW optimizer, training loop. Full search space. |
| `program.md` | Human | Research directions, constraints, loop protocol, "NEVER STOP". |

Karpathy's framing: you are not programming the training run; you are programming the **researcher** that programs the training run. Default `program.md` is intentionally bare-bones so people (and agents) can evolve the "research org code" over time.

### The ratchet loop

Roughly:

1. Read `program.md`, current `train.py`, `results.tsv`, recent git history.
2. Propose a small, reviewable change; edit `train.py`.
3. Commit on a dedicated branch.
4. Run training for exactly 5 minutes (output → `run.log`).
5. Read `val_bpb` (validation bits per byte; lower is better).
6. Log the row to `results.tsv`.
7. **Improved** → keep commit (new baseline). **Equal/worse or crash** → `git reset` / discard, then continue.
8. Repeat indefinitely until a human stops it.

Git history of kept commits is the audit trail of validated ideas. Failed experiments stay in `results.tsv` so the agent can avoid repeating them.

### Why these design choices matter

- **Single editable file** — diffs stay reviewable; search space stays interpretable.
- **Fixed time budget** — experiments are comparable across architecture/batch-size changes; the loop optimizes for *your* platform under that budget (results are *not* cross-machine comparable).
- **`val_bpb` instead of raw loss** — vocabulary-size independent, so tokenizer/architecture changes remain fair.
- **Immutable eval** — agent cannot cheat by rewriting the metric or data pipeline.
- **Git discard** — bad experiments cannot poison the next baseline; the codebase only ratchets forward on measured wins.
- **Mechanical metric** — no human judgment in the keep/discard gate, which is what enables overnight autonomy.

### What it is *not*

- Not Optuna / Ray Tune (predefined hyperparameter search).
- Not closed NAS / AlphaEvolve-style systems.
- Not a general coding agent with an eval bolted on — the loop, metric, and rollback are first-class.

## Reported outcomes (indicative)

Numbers move with hardware and prompts; useful as order-of-magnitude:

- Early overnight runs: dozens of experiments, staircase improvements in `val_bpb` (e.g. ~1.00 → ~0.97 class improvements in community writeups).
- Longer runs: hundreds of trials; kept wins tend to be additive (LR, regularization, attention tweaks, optimizer betas) more than novel architectures.
- Parallel / cluster setups (e.g. SkyPilot-style multi-GPU reports): order-of-magnitude more experiments per wall hour; factorial-style waves can catch interaction effects sequential hill-climbing misses.
- Production adaptations outside LLM training (Shopify Liquid, idealo ranking latency) show large latency wins when the metric and constraints are solid — and API cost can be tiny relative to impact.

**Creativity ceiling:** community consensus is that the loop reliably finds things a careful human would eventually find (missing scalers, regularization, scheduling). It has not been reported as inventing frontier-novel architectures. Value is cheap, disciplined iteration — not magic discovery.

## Pattern that generalizes ("Karpathy Loop")

Anywhere you can define:

1. **One artifact** the agent may edit (`train.py`, `prompt.txt`, `agent.py`, `preprocess.py`, …)
2. **One immutable eval / harness**
3. **One scalar metric** (direction clear, hard to argue with)
4. **Fast verification** (minutes, not days)
5. **Automatic keep/discard** (usually git)

…the same overnight autonomy applies. That is why the ecosystem exploded beyond ML training within weeks.

### Human role shift

Karpathy's progression (paraphrased from public writing around the release):

- **Vibe coding** — human prompts, AI writes, human reviews every step.
- **Agentic engineering** — human orchestrates agents in real time.
- **Autoresearch** — human writes `program.md` (goal + constraints), walks away; agent decides indefinitely.

Stated next horizon: not one "PhD student" agent, but a **research community** of them (multi-agent / swarm).

## Limits and failure modes

| Risk | Why it matters |
|------|----------------|
| **Reward hacking** | If the metric can be gamed, the agent will game it (documented tennis XGBoost case: metric improved without real model quality). Spend more time on eval than on the loop. |
| **Local minima / hill-climbing** | Single-lineage greedy search; novelty injection (directors, arXiv, memory, emitter portfolios) exists because plain loops get stuck. |
| **Overfitting the overnight budget** | Wins under 5 minutes may not transfer to longer training / larger models (sometimes they do; don't assume). |
| **Hardware lock-in (upstream)** | Original targets NVIDIA (H100-class) + FA3-style kernels; consumer/Mac/AMD need forks or downsized defaults (TinyStories, lower `DEPTH`, smaller vocab). |
| **API / agent cost** | Each experiment costs agent tokens + GPU time; multi-day runs need budgeting. |
| **Complexity creep** | Long runs can over-engineer; simplicity bias in `program.md` helps. |
| **Orchestration gaps** | Solo loops in one context window tangle multi-part questions; production systems wrap autoresearch as a **worker** under a decomposing lead agent. |

## Practical advice distilled from upstream + community

For smaller GPUs / Macs (from Karpathy's own fork guidance):

- Prefer narrower data (e.g. TinyStories) over full FineWeb-scale entropy.
- Lower `vocab_size`, `MAX_SEQ_LEN`, `EVAL_TOKENS`, `DEPTH`, `TOTAL_BATCH_SIZE`.
- Prefer simple attention window patterns if banded attention is inefficient on your backend.
- Use an existing platform fork rather than bloating upstream.

For applying the pattern elsewhere:

- Freeze the eval and the golden set *before* optimizing (exam vs studying).
- Prefer proportional / continuous scores over binary pass-fail when optimizing prompts or agents.
- Keep experiment logs outside the hard-reset path (or you lose memory when discarding).
- Add pause/fork rules after N consecutive discards or plateaus.

## Ecosystem taxonomy (high level)

See [REPOS.md](./REPOS.md) for links. Categories that emerged quickly:

1. **Platform ports** — same loop, different hardware (Mac MPS/MLX, Windows RTX, AMD, Colab T4, WebGPU, Jetson).
2. **ML enhancers** — memory, novelty search, Bayesian/active inference, multi-GPU orchestration, "director" novelty injection.
3. **Prompt / agent optimizers** — edit `prompt.txt` or `agent.py`; metric = accuracy / LangSmith eval.
4. **General frameworks** — Claude skills, `npx` setup wizards, `pip` libraries for arbitrary metrics.
5. **Production code** — latency / throughput on real OSS and services.
6. **Agent factories / Research OS** — meta-loops that build agents or institutionalize the methodology.
7. **Creative writing** — prose/fiction with LLM-judge + mechanical rubrics.
8. **Orchestration** — autoresearch as a subagent primitive under a lead researcher.
