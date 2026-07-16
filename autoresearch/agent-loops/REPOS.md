# Repos & systems — agent prompts coding agent

Living map of implementations where a **non-human prompter** continually prompts coding agents. Not exhaustive.

---

## Product / harness primitives (built-in prompters)

| System | How prompting works |
|--------|---------------------|
| Claude Code `/goal` | Harness re-engages worker; separate judge model checks completion condition |
| Claude Code `/loop` | Cadence-based re-prompt while session alive |
| Claude Code Routines / `/schedule` | Cloud keeps prompting after laptop closes |
| Claude Code [Agent Teams](https://code.claude.com/docs/en/agent-teams) | Lead prompts/assigns teammates via shared task list + mailbox (experimental flag) |
| Claude Code subagents / Task tool | Parent writes spawn prompts; children announce back |
| OpenAI Codex Goals | Persistent objective + completion condition across turns |
| OpenClaw subagents | `maxSpawnDepth: 2` orchestrator pattern; spawn prompts + announce chain ([docs](https://docs.openclaw.ai/tools/subagents)) |

---

## Explicit orchestrators (prompter is an agent)

| Repo / product | Prompter | Coding agents |
|----------------|----------|---------------|
| [gastownhall/gastown](https://github.com/gastownhall/gastown) | Mayor (+ Deacon/Witness patrols) | Polecats in worktrees (`gt sling`, `gt nudge`) |
| [Gas Town by Kilo](https://kilo.ai/docs/code-with-ai/gastown) | Hosted Mayor | Polecats + Refinery review agent |
| [Human-Agent-Society/CORAL](https://github.com/Human-Agent-Society/CORAL) | Manager heartbeats (reflect/pivot) | Multi-harness agents in worktrees + grader |
| [alfonsograziano/auto-agent](https://github.com/alfonsograziano/auto-agent) | Orchestrator agent | Spawns Claude/Kiro in **target** repo per hypothesis |
| [katyella/legio](https://github.com/katyella/legio) | Coordinator / Lead / Supervisor | Builder/Reviewer/Merger in worktrees + mail |
| Claude Agent Teams | Team lead session | Peer teammate sessions |

---

## Loop / harness pattern kits

| Repo | Notes |
|------|-------|
| [cobusgreyling/loop-engineering](https://github.com/cobusgreyling/loop-engineering) | Starters, `loop-init`, patterns for systems that prompt/orchestrate agents |
| [cocodedk/loop-engineering](https://github.com/cocodedk/loop-engineering) | Docs on Cherny three stages (code → prompt agents → write loops) |
| [mingrath orchestration-loop gist](https://gist.github.com/mingrath/d5a0a6a02350025d1e70845e521d7561) | Supervisor + worktree workers + verifier + 2-level caps (paste-ready) |
| [coleam00/ralph-loop-quickstart](https://github.com/coleam00/ralph-loop-quickstart) | Bash Ralph (fixed prompt; ancestor of smart prompters) |
| Anthropic [ralph-loop plugin](https://github.com/anthropics/claude-plugins-official/blob/main/plugins/ralph-loop/README.md) | In-session stop-hook re-prompt |
| [vercel-labs/ralph-loop-agent](https://github.com/vercel-labs/ralph-loop-agent) | SDK wrapper: outer verifyCompletion loop around generateText |
| [snwfdhmp/awesome-ralph](https://github.com/snwfdhmp/awesome-ralph) | Ralph ecosystem list |

---

## Research-arena cousins (prompter policy + coding edits)

| Repo | Notes |
|------|-------|
| [karpathy/autoresearch](https://github.com/karpathy/autoresearch) | `program.md` policy; agent continually proposes coding changes under metric ratchet |
| [ArmanJR-Lab/autoautoresearch](https://github.com/ArmanJR-Lab/autoautoresearch) | Explicit **director** that generates next research prompt for the experiment agent |
| [mutable-state-inc/autoresearch-at-home](https://github.com/mutable-state-inc/autoresearch-at-home) | Swarm coordination / shared best-config across many agent runners |

More forks: [../REPOS.md](../REPOS.md), [../AWESOME_LISTS.md](../AWESOME_LISTS.md).

---

## Choosing by “who writes the next prompt?”

| You want the next prompt written by… | Start here |
|--------------------------------------|------------|
| A timer / fixed template | `/loop`, Ralph bash |
| A judge + goal condition | `/goal` |
| A lead LLM that decomposes work | Gas Town Mayor, Agent Teams, OpenClaw orchestrator |
| A research director | Autoresearch + director fork |
| A cron supervisor over many workers | mingrath orchestration loop / Legio / CORAL |
