# Hands AI — macOS app (Xcode)

A native SwiftUI macOS app: floating frosted-glass panel, animated agent orb,
live tool-call feed, and a full system stats dashboard. Voice in (Apple Speech)
and voice out (AVSpeechSynthesizer, premium British voice if installed for the
Jarvis vibe). Talks directly to a local Ollama server at
`http://127.0.0.1:11434` — no Python daemon in the middle — and calls real
tools in-process.

See `CHAT-2026-07-03.md` for the full session log, architecture decisions, and
test results.

## v0.5.0 — 38 tools

22 new capabilities in `ToolsMac.swift` (total 38):

- **Files**: `search_files` (Spotlight, whole Mac), `search_file_contents`
  (recursive grep), `open_file`, `move_file`, `copy_file`, `trash_file`
  (recoverable delete)
- **Personal**: `calendar_today`, `calendar_add_event`, `reminders_add`,
  `reminders_list`, `add_note`, `send_imessage` (explicit-request-only policy
  in the system prompt)
- **Media/system**: `music` (play/pause/next/current/playlists), `set_volume`,
  `screenshot`, `frontmost_app`, `system_action` (lock/sleep/dark-mode/empty
  trash), `timer_set`
- **Automation**: `run_shortcut` + `list_shortcuts` — Hands AI can run any
  macOS Shortcut, which makes every Shortcut you build a new capability
- **Utility**: `weather` (wttr.in, no key), `calculate` (bc, exact math)

Per-app permission prompts (Calendar, Reminders, Notes, Messages, System
Events, Screen Recording) appear once on first use of each.

## v0.4.0 — Claude backend + nicer voice

- **Claude (Anthropic API) backend** — Settings → Backend lets you switch the
  chat provider between Ollama (local, private) and Claude. Paste an API key
  (`sk-ant-…`), pick a model (Opus 4.8 default, Sonnet 5, Haiku 4.5). Full
  SSE streaming and tool use over raw HTTPS (`ClaudeClient.swift`); all 16
  tools work identically on both backends. If no key is set, the app quietly
  stays on Ollama. Title bar and footer show the active backend + model.
- **Nicer speech** — replies are spoken sentence-by-sentence with natural
  pauses instead of one run-on utterance. (Premium Daniel voice still gives
  the biggest jump — Settings → Voice has the one-click link.)

## v0.3.0 — profiles, Mac control, web, skills

- **Profiles** — switchable personas (Jarvis / Coder / Researcher / Operator +
  custom) each with their own system-prompt persona, preferred model, and
  temperature. Picker in the title bar; editor in Settings → Profiles. Stored
  at `~/Library/Application Support/HandsAI/profiles.json`.
- **Mac control tools** — `open_app`, `list_apps`, `run_applescript`
  (Calendar, Notes, Reminders, Mail, Music, Safari, Finder, System Events…),
  `open_url`, `notify`, `clipboard_read`, `clipboard_write`. Requires the
  Automation permission (prompted per app on first use;
  `NSAppleEventsUsageDescription` + `com.apple.security.automation.apple-events`
  are set).
- **Web tools** — `web_search` (DuckDuckGo results) and `web_fetch` (readable
  page text) so current-events questions come from the live web.
- **Skills** — markdown playbooks in `~/hands-ai-skills/`, seeded on first run
  with daily-briefing, system-checkup, quick-note, focus-mode, and
  research-summary. Format: `# Name`, `> description`, then the steps. The
  agent sees the skill list in its system prompt and pulls a playbook via the
  `use_skill` tool. Manage in Settings → Skills.
- **Streaming replies** — responses render token-by-token: a live bubble in
  Chat and live text under the orb on the Agent panel. Voice still speaks the
  complete reply.
- 16 tools total; the agent loop now allows up to 12 tool turns per request.

## Run

```bash
cd ~/hands-ai-mac
bash setup.sh
```

That installs `xcodegen` (via Homebrew) if needed, generates
`HandsAI.xcodeproj`, and opens it in Xcode. In Xcode press **⌘R**.

If you'd rather not use `xcodegen`, install it any way you like and run:
```bash
xcodegen generate && open HandsAI.xcodeproj
```

## Layout

```
HandsAI/
  HandsAIApp.swift        – @main entry
  AppDelegate.swift       – floating NSPanel + global hotkey + status item
  ContentView.swift       – tabbed shell (Agent / System / Chat)
  Info.plist
  HandsAI.entitlements    – mic + network
  Models/
    AgentState.swift      – agent state machine + AgentStore observable
    Profile.swift
    ToolCall.swift
    SystemStats.swift
  Services/
    OllamaClient.swift    – direct HTTP client to Ollama (incl. content-embedded
                            tool-call rescue for weaker models)
    Tools.swift           – the 16 in-process tool implementations
    SkillsStore.swift
    StatsService.swift    – mach host_statistics / sysctl / pmset sampler
    VoiceService.swift    – AVSpeechSynthesizer + SFSpeechRecognizer
    HotkeyService.swift   – Carbon RegisterEventHotKey for ⌥Space
  Views/
    VisualEffectView.swift      – NSVisualEffectView wrapper
    OrbView.swift               – animated mic orb, per-state visuals
    AgentPanelView.swift        – orb + caption + tool feed + input
    ToolFeedView.swift          – live activity log
    StatsView.swift             – CPU / memory / disk / network / cores / processes
    ChatView.swift              – transcript + input (Bubbles/Plain toggle)
    SelectableConversation.swift – NSTextView-based plain mode for drag-select + ⌘C
    LogoView.swift              – pixel-magician brand mark
    SettingsView.swift          – model picker, voice picker, about
  Assets.xcassets/
    AppIcon.appiconset/   – pixel-art icon at 7 sizes
    BrandLogo.imageset/   – same art for in-app use
    AccentColor.colorset/
```

## Backend

The app talks straight to Ollama. Make sure it's running:
```bash
ollama serve
```

Default model is `devstral:latest` (best native `tool_calls` support in the
installed set); the picker falls back through
`qwen3.6 → qwen2.5-coder → hermes → llama3.1 → llama3.2`. If Ollama is
offline, the app shows a banner with a Retry button — the orb, stats, and
voice still function. Tap the orb or use ⌥Space to toggle the panel.
