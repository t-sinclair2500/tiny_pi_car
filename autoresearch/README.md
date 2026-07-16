# Autoresearch research notes

Notes on [Andrej Karpathy's `autoresearch`](https://github.com/karpathy/autoresearch) and the ecosystem of variants that grew from it.

Released March 2026. The original repo is a minimal single-GPU LLM training harness (derived from [nanochat](https://github.com/karpathy/nanochat)) plus an agent instruction file. An AI coding agent runs overnight experiments; git keeps improvements and reverts failures. Fortune and others dubbed the pattern the "Karpathy Loop."

## Contents

| File | What it covers |
|------|----------------|
| [FINDINGS.md](./FINDINGS.md) | How the loop works, design invariants, strengths/limits, pattern generalizations |
| [REPOS.md](./REPOS.md) | Original + notable forks/variants grouped by category |
| [AWESOME_LISTS.md](./AWESOME_LISTS.md) | Exploration of the GitHub awesome-list catalogs of variants/use cases |
| [agent-loops/](./agent-loops/) | Redone research: **loops/lead agents continually prompt coding agents** (Cherny/Steinberger/Osmani; Gas Town; `/goal`; orchestration loops) |
| [SOURCES.md](./SOURCES.md) | Primary sources and writeups used for these notes |

## One-paragraph summary

**Autoresearch is not a training framework — it is a pattern:** one editable artifact, one immutable eval, one scalar metric, a fixed time budget, and automatic keep/discard via git. Humans edit `program.md` (the "research org" skill); the agent edits `train.py`; neither touches `prepare.py`. The same pattern has been ported to other hardware, prompts, agents, production code, fiction, and general "optimize anything measurable" tools.

## Quick links

- Upstream: https://github.com/karpathy/autoresearch
- Announcement context: [tweet 1](https://x.com/karpathy/status/2029701092347630069), [tweet 2](https://x.com/karpathy/status/2031135152349524125)
- Parent training stack: https://github.com/karpathy/nanochat
- Awesome lists (living catalogs): [webfuse-com](https://github.com/webfuse-com/awesome-autoresearch) · [WecoAI](https://github.com/WecoAI/awesome-autoresearch) · [yibie](https://github.com/yibie/awesome-autoresearch)

*Research snapshot: July 2026. Stars/fork counts drift quickly; treat REPOS.md as a map, not a live leaderboard.*
