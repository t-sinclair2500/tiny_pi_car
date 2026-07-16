# Repos and variants

Curated map of the original project and notable variations. Not exhaustive (thousands of forks exist). Prefer upstream or a well-maintained fork that matches your hardware/goal.

---

## 0. Original

| Repo | Notes |
|------|--------|
| [karpathy/autoresearch](https://github.com/karpathy/autoresearch) | Canonical. Single NVIDIA GPU, `prepare.py` / `train.py` / `program.md`, 5-min budget, `val_bpb`. MIT. |
| [karpathy/nanochat](https://github.com/karpathy/nanochat) | Parent training stack; wider platform patterns (device autodetection, FA fallbacks) useful when forking. |

Upstream "notable forks" (linked from Karpathy's README):

- [miolini/autoresearch-macos](https://github.com/miolini/autoresearch-macos) — macOS
- [trevin-creator/autoresearch-mlx](https://github.com/trevin-creator/autoresearch-mlx) — Apple MLX
- [jsegov/autoresearch-win-rtx](https://github.com/jsegov/autoresearch-win-rtx) — Windows RTX
- [andyluo7/autoresearch](https://github.com/andyluo7/autoresearch) — AMD / ROCm

---

## 1. Platform / hardware ports

Same core loop; substrate swapped for consumer or alternate accelerators.

| Repo | Focus |
|------|--------|
| [miolini/autoresearch-macos](https://github.com/miolini/autoresearch-macos) | PyTorch MPS / macOS compatibility |
| [trevin-creator/autoresearch-mlx](https://github.com/trevin-creator/autoresearch-mlx) | Native Apple MLX training |
| [elementalcollision/autoresearch](https://github.com/elementalcollision/autoresearch) | Dual backend: PyTorch MPS + MLX; Muon on both; hardware autodetection / scaled defaults |
| [jsegov/autoresearch-win-rtx](https://github.com/jsegov/autoresearch-win-rtx) | Windows + consumer NVIDIA RTX |
| [andyluo7/autoresearch](https://github.com/andyluo7/autoresearch) | AMD GPUs |
| [parthwhy/autoresearch-lite](https://github.com/parthwhy/autoresearch-lite) | Free Colab / Kaggle T4; FA3 → SDPA; scaled hyperparams; notebook agent loop |
| [mrcloudchase/autoresearch](https://github.com/mrcloudchase/autoresearch) | Mac MPS + T4 + CUDA multi-target fork |
| [Entrpi/autoresearch-everywhere](https://github.com/Entrpi/autoresearch-everywhere) | Unified cross-platform runtime / presets (MLX + CUDA reference lanes) instead of per-OS forks |
| [lucasgelfond/autoresearch-webgpu](https://github.com/lucasgelfond/autoresearch-webgpu) | Browser / WebGPU (no local Python stack) |
| [ArmanJR-Lab/autoautoresearch](https://github.com/ArmanJR-Lab/autoautoresearch) | Jetson-oriented + **director** novelty injection (see enhancers) |
| [supratikpm/gemini-autoresearch](https://github.com/supratikpm/gemini-autoresearch) | Gemini CLI native; Search grounding; headless overnight flags |

**When to use:** you do not have an H100 and want to keep the original ML experiment semantics.

---

## 2. ML research enhancers (smarter loop)

Still LLM training-shaped, but change how the agent searches or remembers.

| Repo | Focus |
|------|--------|
| [scasella/autoresearch-evo](https://github.com/scasella/autoresearch-evo) | Novelty-search-inspired exploration; persistent memory; structured run review; emitter portfolio (`local_tuner`, `architecture_mutator`, `contrarian`, …) |
| [ArmanJR-Lab/autoautoresearch](https://github.com/ArmanJR-Lab/autoautoresearch) | Go **director**: summarize `train.py` → fetch arXiv abstract → generate research directive (`baseline/` vs `mad-scientist/`) |
| [IgorTavcar/autoresearch](https://github.com/IgorTavcar/autoresearch) | Meta-fork consolidating director + MLX/ANE + continue-pretraining experiments |
| [tonitangpotato/autoresearch-engram](https://github.com/tonitangpotato/autoresearch-engram) | Engram cognitive memory (ACT-R / Hebbian-style recall) around the loop |
| [ErikDeBruijn/autoresearcher2](https://github.com/ErikDeBruijn/autoresearcher2) | Bayesian generative model + active inference / Expected Free Energy over experiments |
| [iii-hq/n-autoresearch](https://github.com/iii-hq/n-autoresearch) | Multi-GPU infra, structured state/API, explore→exploit→combine→ablation phases, near-miss detection |

**When to use:** plain hill-climbing plateaus; you want external novelty, memory, or parallel lab-scale plumbing.

---

## 3. Prompt and agent optimizers

Same ratchet; different editable artifact and metric.

| Repo | Focus |
|------|--------|
| [az9713/autoresearch-prompt-optimization](https://github.com/az9713/autoresearch-prompt-optimization) | Optimize `prompt.txt`; metric = extraction accuracy on fixed tests |
| [rungalileo/autoresearch-for-agents](https://github.com/rungalileo/autoresearch-for-agents) | Adversarial suite freeze + prompt optimization; proportional scoring |
| [hwchase17/autoresearch-agents](https://github.com/hwchase17/autoresearch-agents) | Optimize `agent.py` with LangSmith evals/traces (`run_eval.py` + dataset fixed) |
| [alfonsograziano/auto-agent](https://github.com/alfonsograziano/auto-agent) | Orchestrator repo improves a **separate** target agent repo via golden dataset; branch-per-hypothesis |

**When to use:** prompts or agents with a frozen eval set and a numeric score.

---

## 4. Generalized "optimize anything" frameworks

Extract the pattern from LLM training.

| Repo | Focus |
|------|--------|
| [uditgoenka/autoresearch](https://github.com/uditgoenka/autoresearch) | Claude Code skill (`/autoresearch`); arbitrary mechanical metrics + MCP verification |
| [zkarimi22/autoresearch-anything](https://github.com/zkarimi22/autoresearch-anything) | Interactive `npx` setup → `setup.md` + eval |
| [menonpg/autoloop](https://github.com/menonpg/autoloop) | Python library `autoloop-ai`; target file + metric lambda + budget |
| [krzysztofdudek/ResearcherSkill](https://github.com/krzysztofdudek/ResearcherSkill) | Single `researcher.md` skill; `.lab/` history survives git reset; THINK/TEST/REFLECT + plateau guards |

**When to use:** you want the loop on tests, latency, bundle size, SQL, etc., without cloning the nanochat trainer.

---

## 5. Production / domain applications (illustrative)

Not always public forks of the training repo; applications of the pattern:

| Example | What was optimized |
|---------|-------------------|
| Shopify Liquid (`auto/autoresearch.md` style setups reported publicly) | Theme parse/render latency under test + correctness constraints |
| idealo Learning-to-Rank preprocessing | Latency with bit-identical output constraint |
| Vesuvius Challenge ink detection | Multi-agent loop for scroll ink / generalization |
| Tennis XGBoost case study | Cautionary: metric gaming when eval is leaky |

**Lesson:** constraint + honest metric + discard beat cleverness. Bad metrics produce confident garbage.

---

## 6. Agent factories and Research OS

| Repo | Focus |
|------|--------|
| [Dominien/agent-factory](https://github.com/Dominien/agent-factory) | Research problems → score → build/ship specialized agents; rising ship bar |
| [TenureAI/PhD-Zero](https://github.com/TenureAI/PhD-Zero) | Research OS / skill library (governor, literature, experiments, paper writing) around agent runs |
| [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | Large skill library including autoresearch as one reusable skill; multi-runtime |

---

## 7. Creative writing variants

| Repo | Focus |
|------|--------|
| [itspikabubu/redpen](https://github.com/itspikabubu/redpen) | Prose ratchet with multi-persona scoring; surgical edits; keep only if min score rises |
| [NousResearch/autonovel](https://github.com/NousResearch/autonovel) | Full novel pipeline (bible → draft → revision) with mechanical + LLM-judge loops |
| [sinfiny/Auto-Creative-Reasoning](https://github.com/sinfiny/Auto-Creative-Reasoning) | Evaluation-first fiction rewrite ladders / rubrics |
| [CalvinMagezi/self-evolving-skill](https://github.com/CalvinMagezi/self-evolving-skill) | Evolve brand/writing strategy docs against fixed briefs |

---

## 8. Choosing a starting point

| You have… | Start with… |
|-----------|-------------|
| NVIDIA datacenter GPU, want original experience | [karpathy/autoresearch](https://github.com/karpathy/autoresearch) |
| Apple Silicon | [trevin-creator/autoresearch-mlx](https://github.com/trevin-creator/autoresearch-mlx) or [elementalcollision/autoresearch](https://github.com/elementalcollision/autoresearch) or [Entrpi/autoresearch-everywhere](https://github.com/Entrpi/autoresearch-everywhere) |
| Free cloud T4 | [parthwhy/autoresearch-lite](https://github.com/parthwhy/autoresearch-lite) |
| Stuck in local minima on training | [ArmanJR-Lab/autoautoresearch](https://github.com/ArmanJR-Lab/autoautoresearch) or [scasella/autoresearch-evo](https://github.com/scasella/autoresearch-evo) |
| Want to optimize prompts/agents | [az9713/…](https://github.com/az9713/autoresearch-prompt-optimization), [hwchase17/autoresearch-agents](https://github.com/hwchase17/autoresearch-agents), [alfonsograziano/auto-agent](https://github.com/alfonsograziano/auto-agent) |
| Want a library / skill for any metric | [menonpg/autoloop](https://github.com/menonpg/autoloop), [uditgoenka/autoresearch](https://github.com/uditgoenka/autoresearch), [zkarimi22/autoresearch-anything](https://github.com/zkarimi22/autoresearch-anything) |

Browse all forks from the parent: https://github.com/karpathy/autoresearch/forks

For living, curated catalogs beyond this short map, see [AWESOME_LISTS.md](./AWESOME_LISTS.md) — especially [webfuse-com/awesome-autoresearch](https://github.com/webfuse-com/awesome-autoresearch).
