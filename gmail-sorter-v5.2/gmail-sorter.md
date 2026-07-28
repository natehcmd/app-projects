# Gmail Sorter — Skill Pointer

**Version:** 5.2.0

This file is kept for backwards compatibility with older installs that copied
`gmail-sorter.md` into `~/.claude/skills/`.

**The canonical skill definition is [`SKILL.md`](SKILL.md)** in this repository.
All classification rules, onboarding flow, commands, and label actions live there.

## Install (current method)

Install the skill as a directory so Claude Code picks up the frontmatter:

```bash
mkdir -p ~/.claude/skills/gmail-sorter
cp SKILL.md ~/.claude/skills/gmail-sorter/SKILL.md
```

Then say **"sort my inbox"** in Claude Code.

## If you installed this file previously

Delete your old copy and reinstall from `SKILL.md`:

```bash
rm -f ~/.claude/skills/gmail-sorter.md
mkdir -p ~/.claude/skills/gmail-sorter
cp SKILL.md ~/.claude/skills/gmail-sorter/SKILL.md
```

See [`README.md`](README.md) for full setup (Google Cloud OAuth, Node.js CLI, customization).
