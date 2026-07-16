# Agent prompts coding agent

Fresh research notes on the mid-2026 trend: **you stop prompting the coding agent turn-by-turn**. A loop, harness, or lead agent **keeps prompting coding agents** — deciding what to ask next, reading results, verifying, and repeating.

Parent: [../README.md](../README.md) (Autoresearch). Autoresearch is one arena where this pattern is applied to ML experiments.

## Contents

| File | What |
|------|------|
| [FINDINGS.md](./FINDINGS.md) | What the trend is, layers, who prompts whom, patterns, failure modes |
| [REPOS.md](./REPOS.md) | Systems that implement agent→coding-agent prompting |
| [SOURCES.md](./SOURCES.md) | Primary talks, essays, docs |

## The one-sentence claim

**Loop engineering = replace yourself as the continual prompter of coding agents.** You design the system that discovers work, writes/spawns the next prompt, verifies output, and decides whether to prompt again.
