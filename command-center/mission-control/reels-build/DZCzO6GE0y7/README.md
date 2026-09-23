# DZCzO6GE0y7 — nothing buildable

## Source material

Instagram reel from `@aifornontechies`:

> Comment "STACK" and I'll send you the link
>
> If you install one Claude Code repo, make it this one.
>
> Everything Claude Code, 182K stars, built at Anthropic's hackathon and won.
>
> Inside you get 28 specialized subagents, 119 skills, 60 slash commands,
> 34 rules, 20 plus automated hooks, and 14 MCP servers.
>
> Works across Claude Code, Codex, Cursor, OpenCode, Gemini, and more.

## Why nothing was built

This post is engagement bait, not a spec. It gates the actual payoff (a link
to an external GitHub repo) behind commenting "STACK" and getting DM'd — the
repo's name, URL, and contents are never disclosed in the post itself. The
"content" of the reel is just buzzword counts (28 subagents, 119 skills, 60
slash commands, 34 rules, 20+ hooks, 14 MCP servers) attached to an unnamed
repository. There is no described architecture, workflow, file structure, or
technique anywhere in the text — nothing a coding agent could reconstruct or
implement in good faith without simply guessing at what a stranger's
unlinked repo contains.

Fabricating a plausible-looking "Claude Code mega-repo" (fake subagents,
fake skills, fake slash commands, fake MCP servers) to match these numbers
would misrepresent an actual real-world repository that Nate could later
confuse for the genuine one, or evaluate this pass on. That's worse than
building nothing.

## What would make this buildable

If Nate has (or can get) the actual repo link, a follow-up pass could:
- Clone it and summarize/index the real subagents, skills, and slash
  commands it contains, or
- Use it as a reference to scaffold a small, honestly-labeled example
  subagent/skill/hook for Claude Code, built from Anthropic's own public
  Claude Code docs rather than this post.

No such link was present in the source material, so this pass stops here.

**Result: `built = false`.**

## Web research pass (2026-07-21)

Web search confirms the "182K stars, Anthropic hackathon, 28 subagents, 119
skills" repo is `affaan-m/everything-claude-code` (aka "ECC") — the exact same
repo already investigated earlier this session via `gh api` and declined for
an implausible star-growth pattern (231,538 stars within ~6 months of
creation from a single unknown account, ~3,500 stars/day sustained — well
outside organic growth even for a genuinely hackathon-winning project).
Independent press coverage (Medium, X, YouTube, newsletters) confirms the
underlying "hackathon winner" story is real, but the specific star count
trajectory remains the fraud-signal reason it was declined, not the
project's legitimacy in general. No new action — linking to the existing
decline record, not re-installing.
