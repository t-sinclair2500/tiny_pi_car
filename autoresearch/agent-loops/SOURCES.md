# Sources — agent prompts coding agent

Research pass: July 2026. Focused on **non-human continual prompting of coding agents**, not Ralph trivia alone.

## Origin quotes / naming

- Boris Cherny — Acquired Unplugged / WorkOS (Jun 2026): loops prompt Claude; interface source → agent → loop ([WorkOS recap](https://workos.com/blog/boris-cherny-claude-code-acquired-interview-takeaways))
- Peter Steinberger — design loops that prompt agents (X; quoted across Osmani / PE / TokenJam)
- [Addy Osmani — Loop Engineering](https://addyosmani.com/blog/loop-engineering/) ([Substack](https://addyo.substack.com/p/loop-engineering))
- [Pragmatic Engineer — What is loop engineering?](https://newsletter.pragmaticengineer.com/p/what-is-loop-engineering)
- [Cobus Greyling — Loop Engineering](https://cobusgreyling.substack.com/p/loop-engineering) · [cobusgreyling/loop-engineering](https://github.com/cobusgreyling/loop-engineering)
- [codecentric — Loop vs Harness vs Context Engineering](https://www.codecentric.de/en/knowledge-hub/blog/loop-harness-context-engineering-explained)
- [Towards AI — 4 layers that replaced prompt engineering](https://pub.towardsai.net/the-best-engineers-stopped-writing-prompts-the-4-layers-that-replaced-prompt-engineering-2999a71f6346)
- [Learn Harness Engineering — Lecture 13 (loops)](https://walkinglabs.github.io/learn-harness-engineering/en/lectures/lecture-13-loop-engineering/)
- [The Neuron — Cherny & Cat Wu on agent loops](https://www.theneuron.ai/explainer-articles/claude-code-creators-boris-cherny-and-cat-wu-explain-how-to-use-agent-loops/)
- [TechTimes — Claude Code loop engineering](https://www.techtimes.com/articles/318828/20260622/claude-code-loop-engineering-stop-prompting-start-designing-autonomous-agent-workflows.htm)
- [explainx — harness engineering / loops that prompt](https://explainx.ai/blog/anthropic-engineer-loops-prompts-ai-coding-harness-engineering-2026)
- [Matthew Kruczek — writing loops not prompts](https://matthewkruczek.ai/blog/writing-loops-not-prompts)
- [TokenJam — What is an agent loop?](https://tokenjam.dev/blog/2026-06-08-what-is-an-agent-loop)

## Product docs (prompter mechanisms)

- [Claude Code Agent Teams](https://code.claude.com/docs/en/agent-teams)
- Claude Code `/goal`, `/loop`, Routines (Anthropic docs — “Getting started with loops”, “Automate work with routines”)
- [OpenClaw subagents / orchestrator depth](https://docs.openclaw.ai/tools/subagents)
- Codex Goals (OpenAI Codex docs)

## Orchestrators (agent prompts coding agents)

- [gastownhall/gastown](https://github.com/gastownhall/gastown) · [docs.gastownhall.ai](https://docs.gastownhall.ai/) · [Kilo Mayor docs](https://kilo.ai/docs/code-with-ai/gastown/mayor)
- [Steve Yegge — Welcome to Gas Town](https://steve-yegge.medium.com/welcome-to-gas-town-4f25ee16dd04)
- [Better Stack — Building with Gas Town](https://betterstack.com/community/guides/ai/gas-town-multi-agent/)
- [Human-Agent-Society/CORAL](https://github.com/Human-Agent-Society/CORAL)
- [alfonsograziano/auto-agent](https://github.com/alfonsograziano/auto-agent)
- [katyella/legio](https://github.com/katyella/legio)
- [Ry Walker — autonomous agentic tools compared](https://rywalker.com/research/autonomous-agentic-engineering-tools)
- [Towards AI — five ways Claude Code runs multi-step work](https://pub.towardsai.net/five-ways-claude-code-runs-multi-step-work-the-two-questions-that-pick-the-right-one-1016ab7c8816)

## Build guides (anatomy of prompting loops)

- [mingrath — Orchestration Loop guide](https://gist.github.com/mingrath/d5a0a6a02350025d1e70845e521d7561) (supervisor / SLICE / ISOLATE / CHECKER / 2-level caps)
- [Developers Digest — definitive guide goal/loop/routine](https://www.developersdigest.tech/blog/loop-engineering-definitive-guide)
- [Daniel Moka — Loop Engineering 101](https://craftbettersoftware.com/p/loop-engineering-101)
- [cocodedk three stages](https://github.com/cocodedk/loop-engineering/blob/main/docs/03-three-stages.md)
- DEV — [supervise agents with worktrees + test gates](https://dev.to/battyterm/how-to-supervise-ai-coding-agents-without-losing-your-mind-53m4)

## Ancestor (fixed-prompt continual re-feed)

- Geoffrey Huntley — Ralph on [ghuntley.com](https://ghuntley.com)
- [howaiworks — Ralph technique](https://howaiworks.ai/blog/geoffrey-huntley-ralph-agentic-coding-loop)
- Anthropic [ralph-loop plugin](https://github.com/anthropics/claude-plugins-official/blob/main/plugins/ralph-loop/README.md)
- [snwfdhmp/awesome-ralph](https://github.com/snwfdhmp/awesome-ralph)

## Critiques

- Armin Ronacher — “The Coming Loop” (agent loop vs harness loop; defensive complexity)
- Secondary caution in TechTimes / explainx: unattended loops without verifiers ship bugs + burn tokens

## Related in this tree

- Autoresearch: [../README.md](../README.md)
- Awesome Autoresearch catalogs: [../AWESOME_LISTS.md](../AWESOME_LISTS.md)
