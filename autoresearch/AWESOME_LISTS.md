# Awesome lists for Autoresearch

There are several GitHub "awesome list" repos that catalog Autoresearch variants, forks, and use cases. They overlap but serve different jobs.

## Primary lists (as of July 2026)

| Repo | Stars (approx) | Best for |
|------|----------------|----------|
| [webfuse-com/awesome-autoresearch](https://github.com/webfuse-com/awesome-autoresearch) | ~2.3k | **Classic awesome list of repos/systems** — descendants, ports, research agents, domains |
| [WecoAI/awesome-autoresearch](https://github.com/WecoAI/awesome-autoresearch) | ~1.0k | **Use cases with verifiable traces** (progress charts, PRs, blogs) + a compact forks table |
| [yibie/awesome-autoresearch](https://github.com/yibie/awesome-autoresearch) | ~0.6k | **Largest field guide by industry** — hundreds of entries across category files |

Also seen: mirrors/forks under names like `alvinreal/awesome-autoresearch` (same lineage as Webfuse), plus thinner clones.

Homepage for the Webfuse list: https://www.webfuse.com/autoresearch

---

## 1. webfuse-com/awesome-autoresearch

**What it is:** High-signal curated index of *systems inspired by* `karpathy/autoresearch` — the closest thing to "awesome list of variants."

**Structure (TOC):**

1. General-purpose descendants (skills, plugins, swarm, GEPA-adjacent, AIDE/Weco, …)
2. Research-agent systems (AI Scientist, AutoResearchClaw, CORAL, AgentLaboratory, …)
3. Platform ports and hardware forks (macOS, MLX, Windows RTX, WebGPU, multi-GPU, director/Jetson, Engram, Colab T4, …)
4. Domain-specific adaptations (kernels, voice evals, trading Sharpe, genealogy, growth, sudoku, TPU MFU, …)
5. Evaluation & benchmarks (MLAgentBench, MLE-Bench, MLR-Bench, …)
6. Notable use cases and writeups (Shopify Liquid, Vesuvius, SkyPilot cluster, reward-hacking tennis case, Fortune, …)
7. Related resources (other awesome lists / paper collections)
8. Cross-link to [WecoAI/awesome-autoresearch](https://github.com/WecoAI/awesome-autoresearch)

**Notable entries we did not already catalog heavily:**

- `mutable-state-inc/autoresearch-at-home` — SETI@home-style multi-agent swarm / shared best-config
- `davebcn87/pi-autoresearch` — Pi extension + dashboard; used in Shopify Liquid story
- `RightNow-AI/autokernel` — CUDA kernel optimize loop
- `Human-Agent-Society/CORAL` — parallel agents in git worktrees + shared hub ([paper](https://arxiv.org/abs/2604.01658))
- `kayba-ai/recursive-improve`, `SeeleAI/Thoth`, `leo-lilinxiao/codex-autoresearch` — durable run / resume control planes
- Broader cousins: Sakana AI Scientist, GEPA, ADAS, SICA (self-improving coding agents)

**Inclusion vibe:** Broader than "must be a fork of train.py" — includes self-improving agent papers/systems in the same family tree.

**License:** CC0-1.0

---

## 2. WecoAI/awesome-autoresearch

**What it is:** Curated **use cases with optimization traces**. Every row aims to show what the agent tried (progress chart / PR / blog), not just a final claim.

**Sections:**

- **Use Cases** — LLM training, Shopify Liquid, GPU kernels, voice prompts, baseball biomechanics, tennis XGBoost (reward hacking), RL post-training, Vesuvius scrolls, earth-system formulas, Bitcoin formula search, protein folding (SimplexFold), Flappy Bird agent, …
- **Benchmarks & Evaluation** — ResearchClawBench, FML-bench (finds greedy hill-climb nearly matches fancier tree search)
- **Implementations & Forks** — compact table: original, pi-autoresearch, mlx, win-rtx, autoresearch-at-home, Claude skill, agent-digivolve-harness, auto-agent, CORAL, evo

**Contribution bar:** Prefer a progress chart at minimum; ideal is full exploration trace or Weco Observe dashboard.

**License:** CC0 1.0

**Framing note:** They describe Autoresearch as "at its core, a prompt" (`program.md`) — the portable piece is the keep/discard loop against a metric.

---

## 3. yibie/awesome-autoresearch

**What it is:** Large **industry / application taxonomy**. README aggregates category files; each entry is one sentence (scenario + method + value).

**Coverage counts (from their README, mid-2026):**

| Category | Entries |
|----------|--------:|
| Infra / Skills / Forks | 136 |
| Related Practices / Discussions | 152 |
| Scientific Research | 73 |
| Software / Systems Optimization | 52 |
| Finance / Trading | 32 |
| Evaluation / Red Teaming | 24 |
| Workflow Automation | 4 |
| Personal Knowledge / Humanities | 2 |
| Knowledge Base / RAG Preparation | 2 |
| (+ several open categories still empty) | |

**Inclusion criteria (stricter on "is this really autoresearch?"):**

- Public + citable
- Explicitly mentions autoresearch / Karpathy / or shows modify → verify → keep/discard → repeat
- One-sentence scenario/method/value
- Excludes generic research agents with no ratchet loop

**Repo layout:** `categories/*.md`, `CONTRIBUTING.md`, scripts/config for maintaining the aggregate README.

**High-signal domain examples from Scientific Research alone:** robotics (MuJoCo), SLAM, YOLO, medical imaging, photonic design, quantum, drug repurposing (PrimeKG), Ramsey numbers, Vesuvius swarm, Go training, OCR, tabular/Kaggle templates, etc.

---

## How they relate

```
                    ┌─────────────────────────────┐
                    │  karpathy/autoresearch      │
                    └─────────────┬───────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
 webfuse-com/awesome-*      WecoAI/awesome-*         yibie/awesome-*
 (systems & variants)     (cases + traces)        (industry field guide)
         │                        │                        │
         └──────── cross-link ────┘                        │
                    │                                      │
                    └─────────── overlaps on forks / Liquid / Vesuvius / etc.
```

**Practical recommendation:**

- Hunting a **repo/skill/port** → start at [webfuse-com/awesome-autoresearch](https://github.com/webfuse-com/awesome-autoresearch)
- Want **proof a pattern worked** (charts, PRs) → [WecoAI/awesome-autoresearch](https://github.com/WecoAI/awesome-autoresearch)
- Want **breadth by industry** or obscure domain ports → [yibie/awesome-autoresearch](https://github.com/yibie/awesome-autoresearch) (`categories/infra-skills-forks.md` is especially dense for variants)

Our local [REPOS.md](./REPOS.md) is a short starter map; these three lists are the living catalogs.
