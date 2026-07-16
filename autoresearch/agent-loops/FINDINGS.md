# Findings: something else prompts the coding agent

Research redone around the clarification: the trend is not “Ralph bash meme” alone — it is **continual prompting of coding agents by a non-human prompter** (loop, harness, lead/Mayor, `/goal` judge, orchestrator).

---

## 1. What people mean when they say this

Canonical quotes (June 2026 wave):

- **Boris Cherny** (Claude Code): *“I don't prompt Claude anymore. I have loops running that prompt Claude and figuring out what to do. My job is to write loops.”*
- **Peter Steinberger** (OpenClaw): *“You shouldn't be prompting coding agents anymore. You should be designing loops that prompt your agents.”*
- **Addy Osmani** named it **loop engineering**: replace yourself as the person who prompts the agent; design the system that does it instead.

Cherny’s product framing: the interface moved **source code → agent → loop/routine**.

Cobus Greyling’s paraphrase of the same shift: the loop **discovers work, hands tasks to agents (often sub-agents), verifies, persists state, and decides the next action** — on a schedule or until a goal is met. **You are not doing the prompting; you create the routines that do the prompting.**

That is the trend: **prompter role leaves the human and moves into software** (often agent-shaped software).

---

## 2. Vocabulary stack (don’t mash these)

Community consensus (Osmani / Cherny / codecentric / Towards AI “4 layers”):

| Layer | Job | Human used to… |
|-------|-----|-----------------|
| **Prompt** | One message to the model | Type the next instruction |
| **Context** | What fills the window (files, CLAUDE.md, tools) | Paste context by hand |
| **Harness** | Environment around one agent run (tools, permissions, sensors) | Babysit one session |
| **Loop** | System that **repeatedly prompts** the harness/agent without you | Be the outer control loop |

Formula often cited: **Agent = Model + Harness**. Loop engineering sits **one floor above** harness engineering: harness makes a single run reliable; loop makes continuous runs autonomous by **prompting again**.

Mitchell Hashimoto-style framing in writeups: harness = tools + feedback paths; loop = production line that keeps triggering that agent.

**Ralph** sits at the bottom of the loop layer: a dumb outer prompter. **Gas Town / agent teams / orchestration loops** put an **agent** in the prompter seat.

---

## 3. Who prompts whom (the actual architecture)

```
HUMAN
  designs: goal, verifier, budgets, skills, CLAUDE.md
  reviews: final PR / morning report
       │
       ▼
┌─────────────────────────────────────┐
│  PROMPTER (this is the trend)       │
│  can be:                            │
│  • scheduled loop / /goal harness   │
│  • lead / Mayor / coordinator agent │
│  • judge model that re-injects work │
│  • director that writes next task   │
└──────────────────┬──────────────────┘
                   │ writes spawn prompt / sling / nudge
                   ▼
┌─────────────────────────────────────┐
│  CODING AGENT(S)                    │
│  Claude Code / Codex / Cursor / …   │
│  edit files, run tests, commit      │
└──────────────────┬──────────────────┘
                   │ results
                   ▼
         durable state (git, beads, STATE.md, tests)
                   │
                   └── PROMPTER reads this → next prompt
```

**Key test:** if *you* are still typing the next “ok now fix the failing test,” you are still inside the loop. If software decides the next prompt from state + verification, you are doing the trend.

---

## 4. Spectrum of prompters (dumb → smart)

| Prompter | How it chooses the next prompt | Example |
|----------|--------------------------------|---------|
| Fixed file + bash | Same `PROMPT.md` every tick; world changes on disk | Classic Ralph |
| Stop-hook / in-session Ralph | Re-inject same user prompt when agent tries to exit | Claude `ralph-loop` plugin |
| Goal harness + judge | Condition not met → synthetic “continue, because X” | Claude/Codex `/goal` |
| Scheduled routine | Time/event fires a prompt template with fresh repo state | `/loop`, `/schedule`, GitHub Actions |
| Lead / Mayor agent | LLM decomposes goal → writes task prompts → spawns workers | Gas Town, Claude Agent Teams lead, Legio coordinator |
| Orchestration loop | Supervisor wakes on cron, slices backlog, spawns worktree workers, separate verifier grades | mingrath “orchestration loop” pattern |
| Research director | Outer LLM invents experiment directive for inner coding agent | Autoresearch + director forks |
| Heartbeat manager | Interrupts workers with reflect/pivot prompts | CORAL manager |

All of these share one property: **continual prompting of coding agents without a human mid-flight.**

---

## 5. Single loop vs orchestration loop

From the widely copied “orchestration loop” build guide (supervisor + worktree workers + verifier):

### Single-agent loop (5 slots)

| Slot | Question |
|------|----------|
| TRIGGER | When does it run? |
| GOAL | Intent, not steps |
| STOP | Machine-checkable done |
| VERIFY | How work is checked |
| GUARDRAILS | Caps / no-progress / escalate |

Example product form: `/goal all tests in test/auth pass and lint is clean` — after each turn a **separate small model** checks the condition and the harness prompts the worker again if not done.

### Orchestration loop (those 5 + 6 more)

| Slot | Question |
|------|----------|
| SLICE | What is one worker’s job? |
| ISOLATE | Worktrees so workers don’t collide |
| CHECKER | **Different** agent grades (never the author) |
| FLOW | Pipeline vs barrier |
| RECONCILE | Merge pass / triage fail |
| 2-LEVEL CAPS | Cap **per worker** and **whole run** |

Definition from that guide: *“A loop is cron plus a decision-maker in the body. An orchestration loop is a loop whose work-units are other loops.”*

That is “Ralph on steroids” in practice: not a fancier bash one-liner — a **prompter that spawns and re-prompts many coding agents**.

---

## 6. How prompting actually happens (mechanisms)

Concrete ways the prompter “prompts” a coding agent:

1. **Spawn with a task prompt** — lead calls Task/subagent/`sessions_spawn` with a fresh instruction string (OpenClaw orchestrator depth, Claude subagents).
2. **Sling / hook** — put work on an agent’s queue; worker session starts and reads the bead (Gas Town `gt sling`).
3. **Nudge / mail** — inject a message into a live worker session as if the user typed it (`gt nudge`).
4. **Re-inject on stop** — block exit and feed continue/goal feedback (`/goal`, Ralph stop-hook).
5. **Heartbeat interrupt** — manager periodically prompts workers to reflect/pivot (CORAL).
6. **Cron template** — scheduler runs `claude -p "$(cat prompt.md)"` or equivalent with updated state files.

In all cases the coding agent’s next turn starts because **something non-human authored or delivered the prompt**.

---

## 7. Productized forms (what shipped in 2026)

| Primitive | Who prompts the coder? | Stops when |
|-----------|------------------------|------------|
| `/goal` | Harness + independent judge model | Condition true or turn limit |
| `/loop` | Timer fires the same/cadenced prompt | Session ends / you cancel |
| Routines / `/schedule` | Cloud scheduler keeps prompting | You disable the routine |
| Subagents | Parent agent writes spawn prompts | Child announces done |
| Agent Teams (experimental) | Team lead assigns via shared task list + mailbox | Tasks complete / lead shuts down |
| OpenClaw `maxSpawnDepth: 2` | Depth-1 orchestrator spawns depth-2 leaf workers | Announce chain returns |

Important reliability detail from docs/writeups: **`/goal` separates maker and checker** — the model that wrote the code is not the one that decides “done.” Prefer stop conditions tied to **exit codes / files / counts**, not adjectives (“until it’s good”).

Caveat reported in practitioner guides: some Claude `/goal` judges lean on transcript; Codex Goals can bind harder to real command evidence — always make the STOP slot mechanical.

---

## 8. Multi-agent “prompter is an agent” systems

### Gas Town (Yegge / gastownhall)

- **Mayor** = persistent coordinator agent (plans, does not primarily write feature code).
- **Polecats** = ephemeral coding agents in worktrees.
- Mayor **slings** beads onto hooks; can **nudge** workers mid-flight.
- Deacon/Witness = patrol loops that keep prompting health/merge machinery.
- Explicitly: you talk to the Mayor; the Mayor continually prompts/dispatches coding agents.

### Claude Code Agent Teams

- Lead session coordinates; teammates are **separate Claude Code instances**.
- Shared task list + mailbox — lead (and peers) decide next claimed work / messages.
- Different from subagents: peers can talk; not only parent←child announce.

### OpenClaw orchestrator pattern

- `maxSpawnDepth: 2` → main → orchestrator subagent → leaf workers.
- Orchestrator gets spawn/list/history tools; leaves cannot spawn further.
- Push-based announce (don’t poll) — orchestrator prompts next work after children report.

### CORAL

- Agents in worktrees; shared hub of attempts/notes/skills.
- Manager **heartbeat-prompts** agents (reflect / consolidate / pivot).
- Grader daemon scores commits — verification drives what the organization does next.

### auto-agent / similar

- Orchestrator repo agent analyzes failures on a golden set, then **spawns a coding agent inside the target repo** with the next hypothesis prompt; accept/rollback; repeat.

### Legio / Batty / custom supervisors

- Coordinator/supervisor maintains board; spawns builders in worktrees; reviewers validate; mergers integrate.
- Same prompter→coder shape with typed mail / kanban as the prompt channel.

---

## 9. Where Autoresearch fits

Autoresearch is this pattern pointed at ML:

| Role | In Autoresearch |
|------|-----------------|
| Human | Writes `program.md` (standing policy for the prompter) |
| Prompter | Running agent (and optional **director**) choosing next experiment prompt/change |
| Coding agent | Same or nested agent editing `train.py` |
| Verifier | Immutable `prepare.py` + `val_bpb` + git keep/discard |

Director forks make the split explicit: outer LLM **writes the next research directive** that prompts the inner coding/experiment agent. Without a director, one agent plays both prompter and coder under `program.md` — still “loop prompts the coding work,” just not two processes.

See [../FINDINGS.md](../FINDINGS.md).

---

## 10. Why this beat turn-by-turn prompting

| Manual prompting | Loop / lead prompts coder |
|------------------|---------------------------|
| Human latency is the bottleneck | Overnight / multi-hour runs |
| Context stuffed into one chat | Fresh worker contexts + durable state |
| You invent every next step | Prompter invents next step from verify signal |
| Parallelism = you juggling terminals | Prompter slings many isolated workers |

Reported Anthropic-internal style outcomes in secondary writeups (treat as directional, not audited): large share of merged code agent-authored; humans shift to architecture, loop design, and review. The important part for this research is the **role change**, not the exact %.

---

## 11. Failure modes (specific to agent-as-prompter)

| Failure | Mechanism |
|---------|-----------|
| **Infinite re-prompt** | No STOP / no $ ceiling; prompter always finds “one more thing” |
| **Maker grades homework** | Same agent declares done; ships confident wrong |
| **Vague STOP** | “Make it better” → never converges |
| **Prompter thrash** | Lead invents conflicting tasks; workers thrash files (no ISOLATE) |
| **Budget collapse** | No per-worker cap; one stuck leaf burns the whole fleet budget |
| **Prompt spam / overlap** | Bad SLICE; two workers own same files |
| **Context tax** | Bad CLAUDE.md → every prompted worker wastes turns on basics (Cherny “CLAUDE.md tax” discourse) |
| **Defensive rot** | Harness loop keeps patching locally (Ronacher-style critique) |

Hard requirements that show up in every serious guide: **mechanical VERIFY**, **different CHECKER**, **2-level CAPS**, **worktree ISOLATE** for parallel coding agents.

---

## 12. How to think about “Ralph on steroids”

| | Ralph | Steroids version (this trend) |
|--|-------|-------------------------------|
| Prompter | Bash / fixed file | Agent or goal harness that **authors** next prompts |
| Workers | Usually one | Often many, isolated |
| Feedback | Agent reads disk | Prompter + verifier actively rewrite next instruction |
| Product | DIY shell | `/goal`, Agent Teams, Gas Town, Routines, CORAL, … |

Ralph proved continual re-prompting works. The viral 2026 move is putting **decision-making in the prompter**: something that looks at state and **keeps prompting coding agents with new stuff** until a gate says stop.

---

## 13. Practical entry ramp (from research, not vibes)

1. **One self-pacing loop** — `/loop` or bash that re-prompts on build/test failure (feel cost + dumbness).
2. **`/goal` with mechanical STOP** — maker≠checker.
3. **Subagents** — you (or a lead) write spawn prompts for isolated workers.
4. **Orchestration loop** — supervisor + worktrees + separate reviewer + 2-level caps.
5. **Mayor/factory** — Gas Town / Agent Teams when you need persistent coordination of many coding agents.

Do not start at step 5. Each level multiplies failure modes.
