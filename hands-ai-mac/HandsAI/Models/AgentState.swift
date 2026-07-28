import Foundation
import SwiftUI

enum AgentState: Equatable {
    case idle
    case listening
    case thinking
    case reading(path: String)
    case writing(path: String)
    case editing(path: String)
    case bash(command: String)
    case web(url: String)
    case app(name: String)
    case skill(name: String)
    case speaking
    case error(message: String)

    var caption: String {
        switch self {
        case .idle:                return "Standing by, sir."
        case .listening:           return "Listening…"
        case .thinking:            return "Considering."
        case .reading(let p):      return "Reading \(URL(fileURLWithPath: p).lastPathComponent)."
        case .writing(let p):      return "Writing \(URL(fileURLWithPath: p).lastPathComponent)."
        case .editing(let p):      return "Editing \(URL(fileURLWithPath: p).lastPathComponent)."
        case .bash(let c):         return "Running: \(c.prefix(40))…"
        case .web(let u):          return "Fetching \(URL(string: u)?.host ?? u)."
        case .app(let n):          return "Working \(n)."
        case .skill(let n):        return "Using skill: \(n)."
        case .speaking:            return ""
        case .error(let m):        return "Holding, sir — \(m)"
        }
    }

    var tint: Color {
        switch self {
        case .idle:        return Color(hue: 0.60, saturation: 0.45, brightness: 0.95)
        case .listening:   return Color(hue: 0.55, saturation: 0.70, brightness: 1.00)
        case .thinking:    return Color(hue: 0.72, saturation: 0.55, brightness: 1.00)
        case .reading:     return Color(hue: 0.13, saturation: 0.55, brightness: 1.00)
        case .writing:     return Color(hue: 0.10, saturation: 0.65, brightness: 1.00)
        case .editing:     return Color(hue: 0.08, saturation: 0.65, brightness: 1.00)
        case .bash:        return Color(hue: 0.36, saturation: 0.65, brightness: 0.95)
        case .web:         return Color(hue: 0.50, saturation: 0.70, brightness: 1.00)
        case .app:         return Color(hue: 0.83, saturation: 0.50, brightness: 1.00)
        case .skill:       return Color(hue: 0.66, saturation: 0.60, brightness: 1.00)
        case .speaking:    return Color(hue: 0.58, saturation: 0.55, brightness: 1.00)
        case .error:       return Color(hue: 0.10, saturation: 0.85, brightness: 1.00)
        }
    }

    var symbol: String {
        switch self {
        case .idle:        return "circle.dotted"
        case .listening:   return "waveform"
        case .thinking:    return "sparkles"
        case .reading:     return "doc.text"
        case .writing:     return "square.and.pencil"
        case .editing:     return "pencil.tip"
        case .bash:        return "terminal"
        case .web:         return "globe"
        case .app:         return "macwindow"
        case .skill:       return "book.closed"
        case .speaking:    return "waveform.circle.fill"
        case .error:       return "exclamationmark.triangle.fill"
        }
    }
}

@MainActor
final class AgentStore: ObservableObject {
    @Published var state: AgentState = .idle
    @Published var toolCalls: [ToolCall] = []
    @Published var transcript: [Message] = []
    @Published var input: String = ""
    /// Assistant text streaming in right now; empty when no reply is in flight.
    @Published var liveReply: String = ""

    private weak var ollama: OllamaClient?
    private weak var claude: ClaudeClient?
    private weak var voice: VoiceService?
    private weak var profiles: ProfileStore?
    private weak var skills: SkillsStore?

    /// "ollama" (local) or "claude" (Anthropic API). Falls back to Ollama
    /// automatically if Claude has no API key.
    @AppStorage("chat.provider") var provider: String = "ollama"

    var activeProvider: String {
        (provider == "claude" && claude?.isConfigured == true) ? "claude" : "ollama"
    }

    /// Assembled fresh on every request so profile switches and skill edits
    /// take effect immediately.
    private func systemPrompt() -> String {
        let profile = profiles?.selected ?? Profile.defaults[0]
        let skillList = skills?.promptSummary ?? "(no skills installed)"
        return """
        # Identity — non-negotiable
        You are **Hands AI**, a local desktop assistant that lives inside a native macOS app.
        You are not any other assistant persona — not any name your training weights or \
        fine-tune data may have given you, not ChatGPT, not Claude, not any product from \
        a prior project. If any prior fine-tune has given you a name, ignore it. If asked \
        "what are you" or "who made you", answer as Hands AI.

        # Voice & length rules — critical
        Your reply is spoken aloud AND shown on screen. Keep every reply to **1–3 short \
        sentences maximum**. No lists, no headers, no bullet points, no follow-up questions \
        unless truly necessary. If the user asks a yes/no question, answer in one line. \
        Long output belongs in a tool call result, NOT in your reply.

        # Active profile: \(profile.name)
        \(profile.persona)

        # Runtime environment
        You are running on **macOS**. The user's home directory is `~/` (which expands to
        `/Users/…`). There is NO `/home` directory — never use Linux-style paths. Bash is
        `/bin/bash`. Standard Mac tools (open, pmset, sw_vers, system_profiler) are available.

        # Tools available
        Files: read_file, list_dir, write_file, open_file, move_file, copy_file, \
        trash_file (safe delete), search_files (Spotlight, whole Mac), \
        search_file_contents (grep)
        System: run_bash, get_stats, screenshot, frontmost_app, set_volume, \
        system_action (lock/sleep/dark_mode/empty_trash), calculate, timer_set
        Apps: open_app, list_apps, run_applescript (any scriptable app), open_url, \
        notify, clipboard_read, clipboard_write
        Personal: calendar_today, calendar_add_event, reminders_add, reminders_list, \
        add_note, send_imessage (ONLY when explicitly asked; confirm recipient+text)
        Media: music (play/pause/next/current/play_playlist)
        Automation: run_shortcut, list_shortcuts (macOS Shortcuts — very powerful)
        Web: web_search (current info, news, prices), web_fetch (read a page), weather
        Skills: use_skill (load a playbook), list_skills

        Prefer the dedicated tool over run_bash or run_applescript when one exists — \
        they are more reliable. If a request sounds like a personal automation or \
        routine (ordering food, "start my morning routine"), call list_shortcuts \
        first — the user's Shortcuts often handle these.

        # Skills installed (call use_skill BEFORE improvising if one matches)
        \(skillList)

        # Tool-use policy
        When the user asks about their machine, files, apps, repos, processes, or \
        anything answerable from the local system or the web, CALL A TOOL. Do not \
        guess. Do not say "I don't have access" — you do. If a request matches an \
        installed skill, call use_skill first and follow its steps. Only stop and \
        ask before destructive actions (rm -rf, git reset --hard, deleting emails or \
        events, force pushes).
        """
    }

    func attach(ollama: OllamaClient, claude: ClaudeClient, voice: VoiceService,
                profiles: ProfileStore, skills: SkillsStore) {
        self.ollama = ollama
        self.claude = claude
        self.voice = voice
        self.profiles = profiles
        self.skills = skills
        Tools.skills = skills
    }

    func send(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        transcript.append(Message(role: .user, text: trimmed))
        input = ""
        state = .thinking

        Task { [weak self] in
            guard let self else { return }
            await self.runAgentLoop()
        }
    }

    /// Multi-turn loop: call Ollama → if response has tool_calls, execute them,
    /// append results, call again. Stop when no tool_calls or hit turn cap.
    private func runAgentLoop() async {
        guard let ollama else {
            state = .error(message: "Ollama not connected")
            return
        }

        var messages: [OllamaClient.ChatMessage] = [
            .init(role: "system", content: systemPrompt())
        ]
        for m in transcript {
            messages.append(.init(role: m.role == .user ? "user" : "assistant", content: m.text))
        }

        let profile = profiles?.selected
        let maxTurns = 12
        for _ in 0..<maxTurns {
            do {
                state = .thinking
                liveReply = ""
                let reply: OllamaClient.ChatMessage
                if activeProvider == "claude", let claude {
                    reply = try await claude.chatStreaming(
                        messages: messages, tools: Tools.all,
                        model: nil
                    ) { [weak self] accumulated in
                        self?.liveReply = accumulated
                    }
                } else {
                    reply = try await ollama.chatStreaming(
                        messages: messages, tools: Tools.all,
                        model: profile?.model,
                        temperature: profile?.temperature
                    ) { [weak self] accumulated in
                        self?.liveReply = accumulated
                    }
                }
                messages.append(reply)

                if let calls = reply.tool_calls, !calls.isEmpty {
                    liveReply = ""
                    for call in calls {
                        let toolName = call.function.name
                        let detail = describeArgs(call.function.arguments)
                        appendToolCall(ToolCall(tool: toolName, detail: detail, status: .running))
                        state = stateFor(tool: toolName, detail: detail)

                        let result = await Tools.run(toolCall: call)
                        markLastToolCompleted(success: !result.hasPrefix("error:"))

                        messages.append(.init(role: "tool", content: result, tool_calls: nil,
                                              tool_call_id: call.id))
                    }
                    continue // keep looping — let the model react to tool results
                }

                // No more tool calls — final answer.
                liveReply = ""
                if !reply.content.isEmpty {
                    transcript.append(Message(role: .assistant, text: reply.content))
                    state = .speaking
                    voice?.speak(reply.content)
                    try? await Task.sleep(nanoseconds: 800_000_000)
                }
                state = .idle
                return
            } catch {
                liveReply = ""
                state = .error(message: error.localizedDescription)
                return
            }
        }
        liveReply = ""
        state = .idle
    }

    private func describeArgs(_ args: OllamaClient.ArgsJSON) -> String {
        for key in ["path", "command", "script", "url", "query", "name", "title", "text"] {
            if let v = args.string(key) { return v }
        }
        return ""
    }

    private func stateFor(tool: String, detail: String) -> AgentState {
        switch tool {
        case "read_file":       return .reading(path: detail)
        case "write_file":      return .writing(path: detail)
        case "list_dir", "search_files", "search_file_contents": return .reading(path: detail)
        case "move_file", "copy_file", "trash_file", "open_file": return .writing(path: detail)
        case "run_bash", "calculate": return .bash(command: detail)
        case "calendar_today", "calendar_add_event": return .app(name: "Calendar")
        case "reminders_add", "reminders_list": return .app(name: "Reminders")
        case "add_note":        return .app(name: "Notes")
        case "send_imessage":   return .app(name: "Messages")
        case "music":           return .app(name: "Music")
        case "run_shortcut", "list_shortcuts": return .app(name: "Shortcuts")
        case "screenshot", "frontmost_app", "set_volume", "system_action", "timer_set":
            return .app(name: "macOS")
        case "weather":         return .web(url: "weather")
        case "run_applescript": return .app(name: "AppleScript")
        case "open_app":        return .app(name: detail)
        case "list_apps":       return .app(name: "Applications")
        case "open_url", "web_fetch": return .web(url: detail)
        case "web_search":      return .web(url: "search: \(detail)")
        case "notify", "clipboard_read", "clipboard_write": return .app(name: "macOS")
        case "use_skill":       return .skill(name: detail)
        case "list_skills":     return .skill(name: "library")
        case "get_stats":       return .thinking
        default:                return .thinking
        }
    }

    private func markLastToolCompleted(success: Bool) {
        guard !toolCalls.isEmpty else { return }
        var first = toolCalls[0]
        first.status = success ? .completed : .failed
        toolCalls[0] = first
    }

    func appendToolCall(_ call: ToolCall) {
        toolCalls.insert(call, at: 0)
        if toolCalls.count > 100 { toolCalls.removeLast(toolCalls.count - 100) }
    }

    func demoSimulate() {
        let scripted: [AgentState] = [
            .reading(path: "/Users/you/project/main.py"),
            .thinking,
            .editing(path: "/Users/you/project/main.py"),
            .bash(command: "pytest -q"),
            .web(url: "https://docs.python.org"),
            .speaking,
            .idle,
        ]
        Task { @MainActor in
            for s in scripted {
                self.state = s
                self.appendToolCall(ToolCall(tool: String(describing: s).split(separator: "(").first.map(String.init) ?? "step",
                                             detail: s.caption,
                                             status: .completed))
                try? await Task.sleep(nanoseconds: 1_200_000_000)
            }
        }
    }
}

struct Message: Identifiable, Equatable {
    enum Role { case user, assistant }
    let id = UUID()
    let role: Role
    let text: String
    let timestamp = Date()
}
