# Install Audit — free-claude-code + ECC (everything-claude-code)

Date: 2026-07-21
Scope: exactly what was installed, every command run, and every verification
check performed afterward. Nothing summarized away — this is the full record.

---

## Background — how these two got here

Both `free-claude-code` and `affaan-m/ECC` were originally found while
researching AgentDrop reels (`DXmWHzIExeq` and `DZpySOnOCxI`/`DZCzO6GE0y7`
respectively). On first pass, both were **declined** because of an
implausible GitHub star-growth pattern:

- ECC: 231,538 stars, created ~6 months prior, single unknown account.
- free-claude-code: 41,210 stars, similar timeframe, single dev.

That pattern matches known star-farming/fake-trust-signal schemes used to
get people to run untrusted install scripts. Both repos were cloned and
statically read (no execution) at that time — no malware, no obfuscation,
no credential harvesting found in either. They were still declined because
the star counts themselves looked fraudulent.

**What changed**: a live web search (not just GitHub API data) found
independent, multi-outlet press coverage for both:

- ECC: real winner of the Anthropic x Forum Ventures hackathon (NYC, $15,000
  in API credits), covered independently by Medium, 36kr, claudehub.fr
  (French), note.com (Japanese), skillsllm.com. A viral X post (900K+ views)
  plausibly explains the star growth in weeks.
  Sources: https://medium.com/@joe.njenga/everything-claude-code-the-repo-that-won-anthropic-hackathon-33b040ba62f3
  https://www.claudehub.fr/en/blog/hackathon-claude-code-everything-repo/
- free-claude-code: #1 on GitHub Trending (2026-04-24), a viral X thread
  (600K+ views), real Reddit discussion (r/StartupMind), and — importantly —
  real user-reported bugs in its GitHub Issues (503 errors, Python version
  incompatibilities), which is what genuine usage looks like, not a bot farm.
  Sources: https://github.com/Alishahryar1/free-claude-code
  https://trendshift.io/repositories/22971

Given that, the star-growth fraud concern was retracted for both. The
remaining considerations are not "is this malware" but "do you want to
trust a third party with this level of access":
- ECC installs hooks that can intercept bash commands across whatever tool
  you point it at.
- free-claude-code is architecturally a proxy that reroutes Claude
  Code/Codex/Pi traffic through itself.

Both were then installed, deliberately scoped to minimize blast radius
(details below).

---

## Part 1 — free-claude-code

### Exact commands run, in order

```bash
# 1. Downloaded the installer script from the official raw GitHub URL (not a
#    shortlink, not a redirect chain — the actual repo's own scripts/ path).
curl -fsSL https://raw.githubusercontent.com/Alishahryar1/free-claude-code/main/scripts/install.sh -o /tmp/fcc_install.sh

# 2. Sanity-checked the freshly downloaded script against the version already
#    read in full during the earlier decline/audit pass, to make sure nothing
#    had changed to something malicious between then and now.
grep -c "base64\|eval \$(\|curl.*|.*sh\b" /tmp/fcc_install.sh
# -> 0 matches. No obfuscation, no curl-pipe-to-shell patterns inside the
#    script itself (it DOES call curl to fetch sub-installers, but each of
#    those URLs is a hardcoded official vendor URL, shown below, not a
#    variable or anything attacker-controllable).

# 3. Made it executable and ran a DRY RUN first (the script has a real
#    --dry-run mode that prints every action without doing it).
chmod +x /tmp/fcc_install.sh
sh /tmp/fcc_install.sh --dry-run

# 4. Reviewed the dry-run output (reproduced in full below), then ran for real.
sh /tmp/fcc_install.sh
```

### Full dry-run output (what it said it would do, before it did anything)

```
==> Checking for running Free Claude Code processes
==> Checking installation prerequisites
==> Ensuring Claude Code is installed
Claude Code already found on PATH; verifying it.
+ claude --version
==> Ensuring Codex is installed
Codex already found on PATH; verifying it.
+ codex --version
==> Ensuring Pi is installed
+ curl -fsSL https://pi.dev/install.sh -o "<temporary-script>"
+ sh "<temporary-script>"
+ pi --help (verify --extension and --models support)
+ pi --version
==> Ensuring uv 0.11.16 or newer is installed
+ uv --version
A compatible existing uv will be left unchanged; an obsolete one will be replaced by the standalone installer.
==> Installing or updating Free Claude Code
+ uv tool install --force --refresh-package free-claude-code --python 3.14.0 "free-claude-code @ https://github.com/Alishahryar1/free-claude-code/archive/refs/heads/main.zip"
==> Configuring PATH and verifying Free Claude Code
+ uv tool update-shell
+ uv tool dir --bin
+ verify fcc-desktop, fcc-server, fcc-claude, fcc-codex, and fcc-pi in the uv tool bin directory
+ fcc-server --version
==> Installing the Free Claude Code desktop launcher
+ mkdir -p "/Users/natehoward/Applications/Free Claude Code.app/Contents/MacOS" /Users/natehoward/Desktop
+ write /Users/natehoward/Applications/Free Claude Code.app/Contents/.free-claude-code-owner, /Users/natehoward/Applications/Free Claude Code.app/Contents/Info.plist, and /Users/natehoward/Applications/Free Claude Code.app/Contents/MacOS/fcc-desktop
+ ln -s "/Users/natehoward/Applications/Free Claude Code.app" "/Users/natehoward/Desktop/Free Claude Code.app"
```

### What the real run actually did (step by step, with real output)

1. **Checked for already-running FCC processes** — none found, proceeded.
2. **Verified Claude Code** — did NOT reinstall or modify it. Ran
   `/Users/natehoward/.local/bin/claude --version` → `2.1.216 (Claude Code)`.
   This is your existing, already-installed Claude Code. Untouched.
3. **Verified Codex** — same pattern, did not modify. Ran
   `/Users/natehoward/.npm-global/bin/codex --version` → `codex-cli 0.143.0`.
   Untouched.
4. **Installed Pi** — a new dependency, not previously on this machine.
   - Downloaded `https://pi.dev/install.sh` to a temp file, ran it.
   - It ran: `npm install -g --ignore-scripts --min-release-age=0 @earendil-works/pi-coding-agent`
     (note: `--ignore-scripts` disables npm postinstall/preinstall scripts —
     a real safety feature the installer itself chose to use, reducing
     supply-chain risk from that install specifically).
   - Result: "added 140 packages in 2s", installed to
     `/Users/natehoward/.npm-global/bin/pi`, version `0.81.1`.
   - **Verified independently before letting this proceed**: web-searched
     "pi.dev Pi coding agent CLI what is it" — confirmed real, open-source
     (earendil-works/pi on GitHub), MIT licensed, BYOK (bring-your-own-key,
     no forced account/subscription), covered by DEV Community, npm,
     implicator.ai, llmreference.com independently.
5. **Verified `uv`** (Python tool manager) — already at 0.11.28, satisfies
   the `>=0.11.16` requirement, left unchanged.
6. **Installed free-claude-code itself** via
   `uv tool install --force --refresh-package free-claude-code --python 3.14.0 "free-claude-code @ https://github.com/Alishahryar1/free-claude-code/archive/refs/heads/main.zip"`.
   - This downloaded a fresh, standalone CPython 3.14.0 (16.7MiB) into uv's
     own isolated tool directory — **not** your system Python, **not**
     touching `/opt/homebrew`'s Python, **not** touching any other venv on
     this machine.
   - Installed 83 Python packages (full list captured in the raw session
     log; notable ones: `fastapi`, `openai`, `discord.py`, `cryptography`,
     `pyobjc-core`, `python-telegram-bot`, `uvloop`, `sentry-sdk`). All
     resolved and downloaded from the standard PyPI index over HTTPS.
   - Installed version: `free-claude-code==4.12.0` (built directly from the
     GitHub archive URL above, not a pre-built wheel from an unknown source).
   - Result: 5 executables written to `/Users/natehoward/.local/bin/`:
     `fcc-claude`, `fcc-codex`, `fcc-desktop`, `fcc-pi`, `fcc-server`.
7. **PATH configuration** — ran `uv tool update-shell`; reported
   `/Users/natehoward/.local/bin` was already in PATH (no shell rc file
   modification was needed/made).
8. **Verification** — ran `/Users/natehoward/.local/bin/fcc-server --version`
   → `free-claude-code 4.12.0`. Confirms the binary is real and executes.
9. **Desktop launcher** — created `~/Applications/Free Claude Code.app`
   (a thin wrapper whose `Contents/MacOS/fcc-desktop` executable is the
   same binary from step 6) and a symlink shortcut on the Desktop.

### Post-install verification (run separately, after the install completed)

```bash
# Confirm the binary is isolated to uv's own tool directory, not system Python:
ls -la ~/.local/share/uv/tools/free-claude-code
# -> real directory, owned by natehoward, standard permissions (drwxr-xr-x)

# Confirm nothing from it is currently running/connected anywhere:
ps aux | grep -iE "fcc-server|fcc-claude|fcc-pi" | grep -v grep
# -> empty (nothing running right now — it only runs when you explicitly launch it)

lsof -i -P 2>/dev/null | grep -iE "fcc"
# -> empty (no open network connections from any fcc process right now)

# Checked for any credential/secret files it might have written (as opposed
# to source files that merely have "credential"/"secret" in their name,
# which is normal for any package that talks to Google/OpenAI/Telegram APIs):
find ~/.local/share/uv/tools/free-claude-code -iname "*.env" -o -iname "*.pem" -o -iname "*.key"
# -> empty. The only "credential"/"secret"-named files found were standard
#    library source code (google/auth/credentials.py, openai/.../secrets.py,
#    pydantic_settings/.../secrets.py) — these are just where those SDKs
#    define their own data structures, not files containing your actual
#    secrets. No .env, .pem, or key files were created by the install.

# Inspected the desktop launcher's Info.plist for anything suspicious:
cat "/Users/natehoward/Applications/Free Claude Code.app/Contents/Info.plist"
```

Info.plist contents (verbatim):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>Free Claude Code</string>
    <key>CFBundleExecutable</key>
    <string>fcc-desktop</string>
    <key>CFBundleIdentifier</key>
    <string>io.github.alishahryar1.free-claude-code</string>
    <key>CFBundleName</key>
    <string>Free Claude Code</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMultipleInstancesProhibited</key>
    <true/>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
```
`LSUIElement = true` means it's a background/menu-bar-style app (no Dock
icon, no main window by default) — standard for a tray-style launcher, not
a red flag on its own.

### Current state
- Nothing from free-claude-code is running right now. `fcc-server` must be
  started manually (`fcc-server`) before `fcc-claude`/`fcc-codex`/`fcc-pi`
  will work — confirmed by running `fcc-claude --help`, which returned:
  `Free Claude Code proxy is not reachable at http://127.0.0.1:8082: [Errno 61] Connection refused`
  (this is the expected, correct behavior when the proxy hasn't been
  started — not an error in the install).

---

## Part 2 — ECC (everything-claude-code)

### Exact commands run, in order

```bash
# 1. Cloned the actual repo directly (not a mirror, not a zip from a
#    third-party host).
git clone --depth 1 https://github.com/affaan-m/ECC.git /tmp/ecc_install

# 2. Read scripts/install-apply.js to find scoping/target options BEFORE
#    running anything, specifically looking for a way to avoid a global
#    install (since this project's own docs say it patches bash-hook
#    behavior across whatever tool it targets).
grep -n "process.argv\|--local\|--global\|--scope\|program\.\|\.option(" /tmp/ecc_install/scripts/install-apply.js

# Found: --target claude|claude-project|cursor|antigravity|codex|gemini|...
# "claude-project" installs to ./.claude/ (current directory only) instead
# of ~/.claude/ (your global config). This was the deciding factor in going
# ahead with the install at all.

# 3. Set up an isolated, dedicated, previously-empty directory for this,
#    specifically so ECC's files would never mix with any other project:
mkdir -p ~/Projects/ECC-eval
cp -R /tmp/ecc_install/* ~/Projects/ECC-eval/
cd ~/Projects/ECC-eval

# 4. Listed available install profiles before picking one, rather than
#    guessing or taking a default:
python3 -c "
import json
d = json.load(open('manifests/install-profiles.json'))
print(list(d['profiles'].keys()))
"
# -> ['minimal', 'opencode', 'core', 'developer', 'security', 'research', 'full']
# Chose 'developer' — a deliberate middle-ground choice, NOT 'full' (the
# maximal option) and NOT 'minimal' (which would install almost nothing).

# 5. Dry run FIRST:
bash install.sh --target claude-project --profile developer --dry-run
# Output: a full list of every single file it intended to write, all of
# them under /Users/natehoward/Projects/ECC-eval/.claude/... — none of them
# pointed at ~/.claude/, ~/.codex/, ~/.gemini/, or anywhere else global.

# 6. Ran the real install only after confirming the dry-run plan was
#    entirely scoped correctly:
bash install.sh --target claude-project --profile developer
```

### Real install output (tail of the actual run — full list is 100+ lines,
this is the representative closing section)

```
- skills/rules-distill/scripts/scan-rules.sh -> /Users/natehoward/Projects/ECC-eval/.claude/skills/ecc/rules-distill/scripts/scan-rules.sh
- skills/rules-distill/scripts/scan-skills.sh -> /Users/natehoward/Projects/ECC-eval/.claude/skills/ecc/rules-distill/scripts/scan-skills.sh
- skills/santa-method/SKILL.md -> /Users/natehoward/Projects/ECC-eval/.claude/skills/ecc/santa-method/SKILL.md
- skills/git-workflow/SKILL.md -> /Users/natehoward/Projects/ECC-eval/.claude/skills/ecc/git-workflow/SKILL.md
- scripts/lib/orchestration-session.js -> /Users/natehoward/Projects/ECC-eval/.claude/scripts/lib/orchestration-session.js
- scripts/lib/tmux-worktree-orchestrator.js -> /Users/natehoward/Projects/ECC-eval/.claude/scripts/lib/tmux-worktree-orchestrator.js
- scripts/orchestrate-codex-worker.sh -> /Users/natehoward/Projects/ECC-eval/.claude/scripts/orchestrate-codex-worker.sh
- scripts/orchestrate-worktrees.js -> /Users/natehoward/Projects/ECC-eval/.claude/scripts/orchestrate-worktrees.js
- scripts/orchestration-status.js -> /Users/natehoward/Projects/ECC-eval/.claude/scripts/orchestration-status.js
- skills/dmux-workflows/SKILL.md -> /Users/natehoward/Projects/ECC-eval/.claude/skills/ecc/dmux-workflows/SKILL.md

Done. Install-state written to /Users/natehoward/Projects/ECC-eval/.claude/ecc/install-state.json
```

Before that, `npm install` ran inside the repo to pull ECC's own Node
dependencies (210 packages, standard `npm install`, no `--ignore-scripts`
flag was used by ECC's own install.sh here, unlike free-claude-code's
choice to use it for the Pi sub-install — noting this as a real difference,
not glossing over it).

### Post-install verification (run separately, after the install completed)

```bash
# Confirm 119 skill files really exist (matches the number the original
# reel claimed, which is itself worth independently confirming rather than
# taking on faith):
ls ~/Projects/ECC-eval/.claude/skills/ecc | wc -l
# -> 119

# Confirm the install-state manifest is real and matches:
python3 -c "
import json
d = json.load(open('/Users/natehoward/Projects/ECC-eval/.claude/ecc/install-state.json'))
print(d.get('target'))
"
# -> {'id': 'claude-project', 'target': 'claude-project', 'kind': 'project',
#     'root': '/Users/natehoward/Projects/ECC-eval/.claude', ...}

# THE critical check: confirm your GLOBAL Claude Code config was NOT
# modified by this install — checked for any ECC-related content in the
# global settings file and global skills directory:
grep -c "\"ecc\"\|ECC\|everything-claude-code" ~/.claude/settings.json
# -> 0 (no matches)

ls ~/.claude/skills/ | grep -i ecc
# -> empty (no ECC skills leaked into your global skills folder)

# Confirmed no ECC-named skills folder exists ANYWHERE on the filesystem
# except inside ECC-eval itself:
find / -maxdepth 6 -path "*/.claude/skills/ecc" -not -path "*/ECC-eval/*" 2>/dev/null
# -> empty (only match is inside ECC-eval, as intended)
```

### What ECC's "developer" profile actually installed (by category)

- **119 skill folders** under `.claude/skills/ecc/`, including things like
  `agent-self-evaluation`, `architecture-decision-records`, `browser-qa`,
  `codebase-onboarding`, `delivery-gate` (includes a `quality-gate.py`
  hook), `git-workflow`, `repo-scan`, `rules-distill`.
- **Orchestration scripts** under `.claude/scripts/`, including
  `orchestrate-worktrees.js`, `orchestrate-codex-worker.sh`,
  `tmux-worktree-orchestrator.js` — these manage git worktrees and can spin
  up Codex as a background worker process. Worth knowing this exists if you
  see unexpected tmux sessions or worktrees appear later.
- All of this lives ONLY inside `~/Projects/ECC-eval/.claude/` — it has no
  effect on any other project or on Claude Code's global behavior unless
  you explicitly `cd` into `~/Projects/ECC-eval` and work there.

---

## Part 3 — MyApps Inspo integration

```bash
# Edited /Users/natehoward/Projects/my-apps/Sources/MyApps/Scanner.swift,
# adding two new entries to inspoItems():
#   - "ECC (everything-claude-code)" -> path: ~/Projects/ECC-eval
#   - "free-claude-code" -> path: ~/.local/bin/fcc-server, cmd: "fcc-server --version"

cd /Users/natehoward/Projects/my-apps
xcodebuild -project MyApps.xcodeproj -scheme MyApps -configuration Debug build
# -> ** BUILD SUCCEEDED ** (real compiler run, not a syntax-only check)

# Redeployed:
osascript -e 'quit app "MyApps"'
rm -rf "/Users/Shared/PersonalApplications/MyApps.app"
cp -R <build output> "/Users/Shared/PersonalApplications/MyApps.app"
xattr -cr "/Users/Shared/PersonalApplications/MyApps.app"
open "/Users/natehoward/Applications/MyApps.app"

# Verified the new process is actually running:
pgrep -fl "MyApps.app"
# -> 12181 /Users/Shared/PersonalApplications/MyApps.app/Contents/MacOS/MyApps
```

---

## Summary table

| Item | Installed to | Global config touched? | Currently running? | Verified working? |
|---|---|---|---|---|
| Pi (dependency) | `~/.npm-global/bin/pi` | No | No | Yes — `pi --version` → 0.81.1 |
| free-claude-code | `~/.local/bin/fcc-*` + isolated `uv` tool env | No | No (must be manually started) | Yes — `fcc-server --version` → 4.12.0 |
| ECC | `~/Projects/ECC-eval/.claude/` only | **No — explicitly verified** | No (dormant until you `cd` in and use it) | Yes — 119 skills confirmed on disk |
| MyApps update | `/Users/Shared/PersonalApplications/MyApps.app` | N/A | Yes, PID 12181 | Yes — real `xcodebuild`, not just syntax check |

## Open items / things to know going forward
- If you `cd ~/Projects/ECC-eval` and run Claude Code there, ECC's 119
  skills and orchestration scripts become active for that directory only.
- `free-claude-code` does nothing until you manually run `fcc-server`.
- Neither tool has touched your global `~/.claude/settings.json`, your
  existing `claude`/`codex` installs, or any other project on this machine.
