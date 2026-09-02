# handoff.py — a session handoff system for Claude Code (avoid context rot)

## Source note

This tool is inferred from an Instagram reel (`@joestoltelive`) whose caption
promised "one of the most overlooked Claude Code tips... this simple handoff
system helps Claude stay focused, avoid repeated mistakes." The reel itself
was a comment-to-DM lead-gen hook ("Comment CLEAR and I'll send you the full
guide") and disclosed zero concrete mechanics. Rather than build nothing, this
implements the standard, well-known version of the pattern it's gesturing
at — a living handoff file that survives across coding sessions — since that's
a real and useful technique regardless of what the original poster's private
DM guide actually contains.

## What it does

Long agent coding sessions suffer from "context rot": as the conversation
grows, the model's effective attention to early decisions/gotchas degrades,
leading to repeated mistakes, forgotten rationale, or wasted tokens
re-deriving things it already figured out.

The fix is low-tech: keep a single `HANDOFF.md` file in your project as
**compressed working memory** between sessions. When a session's context is
getting long (or you're about to end one), you log the essentials — current
task, decisions made, gotchas hit, next steps — and optionally auto-append a
git-based snapshot of what changed. When you start a *new* Claude Code
session, the first instruction is: **"Read HANDOFF.md before doing
anything else."** The new session starts with a small, curated summary
instead of either (a) no memory at all, or (b) a giant re-read of the whole
prior transcript.

This script is just a thin CLI for maintaining that file consistently, so
the habit is easy to keep (one command per note, instead of hand-editing
markdown mid-task).

## How to run it

Requires only Python 3 (stdlib only — no dependencies to install). `git` is
optional; it's used for the `snapshot` command's auto-diff-summary, and the
tool degrades gracefully without it.

Run it from the root of the project you're working on (it reads/writes
`HANDOFF.md` in the current directory):

```bash
# one-time setup in a project
python3 /path/to/handoff.py init

# during a session, log things as they happen
python3 /path/to/handoff.py task "Refactor auth module to use JWT"
python3 /path/to/handoff.py decision "Using PyJWT, not python-jose (fewer deps)"
python3 /path/to/handoff.py gotcha "Tests fail if TZ != UTC — set env var in CI"
python3 /path/to/handoff.py next "Wire up refresh-token endpoint"

# before wrapping up / when context is getting long, snapshot git state
python3 /path/to/handoff.py snapshot

# print the current handoff file
python3 /path/to/handoff.py show

# start a fresh handoff (archives the old one to .handoff_archive/)
python3 /path/to/handoff.py clear
```

Tip: alias it for convenience, e.g. `alias ho="python3 /path/to/handoff.py"`,
so logging a decision mid-session is just `ho decision "..."`.

### Using it with Claude Code

1. Drop `handoff.py` somewhere on your `$PATH` (or reference it by full path)
   inside a project.
2. At the start of any new Claude Code session on that project, tell it:
   *"Read HANDOFF.md first, then proceed."* (You can also put that
   instruction directly in your project's `CLAUDE.md` so it happens
   automatically.)
3. As you (or the agent) work, periodically log task/decision/gotcha/next
   entries — either you run the commands yourself, or you can ask Claude Code
   to run them for you as it works ("log that decision to the handoff file").
4. Before ending a long session, run `snapshot` so the next session sees
   exactly what changed since the last checkpoint.

## Setup / API-key notes

None. This is a pure local file-management CLI — no network calls, no API
keys, no external services. The only optional integration is your local
`git` binary (already present on virtually any dev machine), used purely
read-only (`git status`, `git log`, `git rev-parse`) to summarize repo state.
It never writes to git history or makes commits.
