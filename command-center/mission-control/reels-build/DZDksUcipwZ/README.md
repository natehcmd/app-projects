# skill_audit.py — safety-check a Claude Agent Skill before you install it

## Where this came from

The source reel (`@liamjohnston.ai`, shortcode `DZDksUcipwZ`) is mostly
engagement bait: it hypes "Agent Skills" and a marketplace of "thousands" of
them, then gates the actual guide and link behind "Comment SKILLS and I'll
DM you." No concrete tool, command, or URL is ever named in the transcript.

Buried in the hype, though, is one real and useful idea, stated plainly:

> "The catch nobody talks about is that skills can run code on your machine.
> Some of them touch your files, your shell, even your API keys. The
> marketplace does not check them for you... Audit it for safety before you
> install."

That's a legitimate, buildable concept — Claude Agent Skills (and similar
plugin systems) are just folders of Markdown + scripts, and a skill you
install can contain a `subprocess.run(...)`, a `curl | bash`, or a line that
reads `~/.aws/credentials`. Nobody automatically checks that for you. So
instead of chasing the DM-gated "guide," this builds the actual auditing
step the reel gestures at.

## What it does

`skill_audit.py` is a small, local, static-analysis CLI. Point it at a
skill folder (or a `.zip` of one) that you've **already downloaded**, and it:

1. Looks for `SKILL.md` (the manifest Claude Agent Skills use).
2. Walks every script file in the package (`.py .sh .js .ts .mjs .cjs .rb .pl .ps1`).
3. Greps for patterns commonly associated with risky behavior:
   - **HIGH** — shell/OS execution, `curl | bash`-style installers,
     credential/secret file access (`.ssh`, `.aws/credentials`, `.env`,
     `.pem`, API/secret key strings), dynamic `eval`/`exec`, reverse-shell
     patterns.
   - **MEDIUM** — outbound network calls, reading environment variables,
     writes to absolute paths outside the skill folder, suspicious base64
     blobs.
   - **LOW** — `sudo`, recursive deletes.
4. Prints a plain-English report with `file:line` citations and *why* each
   pattern matters, plus an overall risk rating.
5. Optionally writes the same report as JSON (`--json report.json`) so you
   can wire it into a pre-install check or CI step.

It exits `0` (clean), `1` (medium findings), or `2` (high findings) so it
can gate a script if you want.

**What it deliberately does not do:** it does not download skills, browse
any marketplace, bypass any login/paywall, or execute anything from the
skill it's scanning. It only reads files that are already sitting on your
disk. You're responsible for how you obtained them (e.g. `git clone`,
downloading a `.zip` from wherever you found the skill).

## How to run it

Requires only Python 3.9+ (standard library — no dependencies to install).

```bash
# Audit a skill folder you've downloaded/cloned
python3 skill_audit.py /path/to/some-skill

# Audit a .zip of a skill without unzipping it yourself
python3 skill_audit.py /path/to/some-skill.zip

# Also save a JSON report
python3 skill_audit.py /path/to/some-skill --json report.json
```

### Try it on the included examples

Two fixture "skills" are included under `examples/` purely to demo the tool:

```bash
# Should come back HIGH RISK (fake creds exfil + curl|bash + subprocess)
python3 skill_audit.py examples/risky-skill

# Should come back clean
python3 skill_audit.py examples/clean-skill
```

Neither fixture does anything real — `risky-skill` is just text patterns
inside plain `.sh`/`.py` files so the scanner has something to flag; nothing
in this repo executes those scripts, it only reads them as text.

## Setup / API-key notes

None. This tool makes zero network calls and needs zero credentials — it's
pure local static analysis (regex over text files). That's also exactly why
you shouldn't treat a clean scan as a certificate of safety: it's a
heuristic first pass, not a sandboxed dynamic analysis or a substitute for
actually reading `SKILL.md` and the scripts it references before you trust
a skill with your shell and your files.

## Limitations (read this before trusting a "clean" result)

- Regex-based — it can miss obfuscated or cleverly split-up risky code, and
  it can false-positive on legitimate uses (e.g. a skill that *legitimately*
  needs `subprocess` to run tests, or the word "secret" in a comment).
- It doesn't execute anything, so it can't catch behavior that only
  manifests at runtime (e.g. a script that downloads and evals a second
  payload only under certain conditions).
- It only scans common script extensions plus `SKILL.md`; it won't inspect
  compiled binaries, arbitrary data files, or code fetched at runtime from
  elsewhere.
- Treat a "NO FLAGS" result as "nothing obviously alarming jumped out," not
  as "verified safe."
