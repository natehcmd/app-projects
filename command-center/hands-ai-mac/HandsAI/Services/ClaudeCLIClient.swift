import Foundation
import SwiftUI

/// Backend that shells out to the real `claude` CLI (Claude Code) in
/// non-interactive `--print --output-format stream-json` mode, so Hammond's
/// agent gets actual Claude Code tool use (Bash, Read, Edit, WebFetch,
/// WebSearch) instead of just chat-with-custom-tools.
///
/// Runs in `--bare` mode (skips hooks, auto-memory, CLAUDE.md discovery, and
/// the user's personal skills/MCP servers — confirmed live: without --bare a
/// spawned `claude` inherits the user's ENTIRE interactive Claude Code
/// environment, which is wrong for an embedded assistant feature) using its
/// own Anthropic API key rather than the signed-in OAuth session, so this is
/// a clean, fast, isolated agent call — not a shared session with whatever
/// else the user runs claude for. Requires the same key already entered for
/// the direct-API backend (Settings → Backend → Claude).
///
/// The CLI runs its own multi-turn tool-calling loop internally and streams
/// JSON events as it goes — it does NOT hand tool calls back to us to
/// execute, unlike Ollama/ClaudeClient. So `chatStreaming` here always
/// returns `tool_calls: nil`; live tool activity is reported separately via
/// `onToolEvent` so the UI can still show it happening.
@MainActor
final class ClaudeCLIClient: ObservableObject {
    @AppStorage("claudeCLI.model") var selectedModel: String = "claude-opus-4-8"
    /// Comma-separated tool names/patterns (e.g. "Bash(git *)") allowed to run
    /// without a permission prompt. Non-interactive mode can't show prompts,
    /// so anything not on this list (and not covered by `skipPermissions`)
    /// is simply denied by the CLI.
    @AppStorage("claudeCLI.allowedTools") var allowedTools: String =
        "Read,Grep,Glob,WebFetch,WebSearch,Bash(ls *),Bash(cat *),Bash(pwd),Bash(git status),Bash(git log *),Bash(git diff *),Bash(find *)"
    /// Off by default. When on, passes --dangerously-skip-permissions instead
    /// of the allowlist above — full autonomy, no confirmation of any kind.
    @AppStorage("claudeCLI.skipPermissions") var skipPermissions: Bool = false
    @AppStorage("claudeCLI.sessionID") private var sessionID: String = ""

    @Published var resolvedPath: String?
    @Published var resolveError: String?

    var isConfigured: Bool { resolvedPath != nil }

    init() {
        Task { await resolvePath() }
    }

    /// GUI apps don't inherit the login shell's PATH, so a bare Process
    /// launch of "claude" won't find it. Resolve an absolute path once
    /// (checking common install locations first, then a login shell) and
    /// cache it — same class of problem `Tools.swift`'s subprocess tools
    /// already sidestep with hardcoded absolute paths.
    private func resolvePath() async {
        let candidates = [
            "\(NSHomeDirectory())/.local/bin/claude",
            "/opt/homebrew/bin/claude",
            "/usr/local/bin/claude",
        ]
        for c in candidates where FileManager.default.isExecutableFile(atPath: c) {
            resolvedPath = c
            return
        }
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/bin/zsh")
        proc.arguments = ["-l", "-c", "command -v claude"]
        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = Pipe()
        do {
            try proc.run()
            proc.waitUntilExit()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            let path = String(data: data, encoding: .utf8)?
                .trimmingCharacters(in: .whitespacesAndNewlines)
            if let path, !path.isEmpty, FileManager.default.isExecutableFile(atPath: path) {
                resolvedPath = path
            } else {
                resolveError = "Couldn't find the `claude` CLI on this Mac (checked ~/.local/bin, Homebrew, and PATH)."
            }
        } catch {
            resolveError = "Couldn't resolve the `claude` CLI: \(error.localizedDescription)"
        }
    }

    /// Drops the stored session id — the next call starts a fresh Claude Code
    /// conversation instead of resuming. Exposed for a "New session" button
    /// in Settings, and used internally to recover from an expired/invalid
    /// resume id instead of getting stuck failing forever.
    func resetSession() { sessionID = "" }

    func chatStreaming(messages: [OllamaClient.ChatMessage],
                       apiKey: String,
                       model: String? = nil,
                       onDelta: @escaping (String) -> Void,
                       onToolEvent: @escaping (ToolCall) -> Void) async throws -> OllamaClient.ChatMessage {
        guard let claudePath = resolvedPath else {
            throw NSError(domain: "ClaudeCLI", code: -1,
                          userInfo: [NSLocalizedDescriptionKey: resolveError ?? "claude CLI not found."])
        }
        let key = apiKey.trimmingCharacters(in: .whitespaces)
        guard !key.isEmpty else {
            throw NSError(domain: "ClaudeCLI", code: 401,
                          userInfo: [NSLocalizedDescriptionKey: "No Claude API key set (Settings → Backend → Claude)."])
        }
        guard let userMessage = messages.last(where: { $0.role == "user" })?.content,
              !userMessage.isEmpty else {
            throw NSError(domain: "ClaudeCLI", code: -2,
                          userInfo: [NSLocalizedDescriptionKey: "No user message to send."])
        }
        let systemPrompt = messages.first(where: { $0.role == "system" })?.content ?? ""
        let useModel = (model?.isEmpty == false ? model! : selectedModel)

        var args = [
            "-p", userMessage,
            "--output-format", "stream-json",
            "--verbose",
            "--bare",
            "--model", useModel,
        ]
        if !systemPrompt.isEmpty {
            args += ["--append-system-prompt", systemPrompt]
        }
        if skipPermissions {
            args.append("--dangerously-skip-permissions")
        } else {
            let tools = allowedTools.split(separator: ",").map {
                $0.trimmingCharacters(in: .whitespaces)
            }.filter { !$0.isEmpty }
            if !tools.isEmpty { args += ["--allowedTools"] + tools }
        }
        let resumeID = sessionID
        if !resumeID.isEmpty {
            args += ["--resume", resumeID]
        }

        return try await runProcess(path: claudePath, args: args, apiKey: key,
                                    onDelta: onDelta, onToolEvent: onToolEvent)
    }

    private func runProcess(path: String, args: [String], apiKey: String,
                            onDelta: @escaping (String) -> Void,
                            onToolEvent: @escaping (ToolCall) -> Void) async throws -> OllamaClient.ChatMessage {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<OllamaClient.ChatMessage, Error>) in
            let process = Process()
            process.executableURL = URL(fileURLWithPath: path)
            process.arguments = args
            var env = ProcessInfo.processInfo.environment
            env["ANTHROPIC_API_KEY"] = apiKey
            process.environment = env

            let stdout = Pipe()
            let stderr = Pipe()
            process.standardOutput = stdout
            process.standardError = stderr

            // All of this state is only ever touched from `parseQueue` (a
            // serial GCD queue), which is what makes reading it from the
            // stdout handler, the stderr handler, and the termination
            // handler — three different background callbacks — safe.
            // UI-facing calls (onDelta/onToolEvent/sessionID) hop back onto
            // the main actor via `Task { @MainActor in ... }`.
            let parseQueue = DispatchQueue(label: "handsai.claudecli.parse")
            var buffer = Data()
            var finalText = ""
            var gotResult = false
            var errText = ""
            var capturedSessionID: String?

            stdout.fileHandleForReading.readabilityHandler = { handle in
                let data = handle.availableData
                guard !data.isEmpty else { return }
                parseQueue.async {
                    buffer.append(data)
                    while let range = buffer.range(of: Data([0x0A])) {
                        let lineData = buffer.subdata(in: buffer.startIndex..<range.lowerBound)
                        buffer.removeSubrange(buffer.startIndex..<range.upperBound)
                        guard !lineData.isEmpty,
                              let obj = try? JSONSerialization.jsonObject(with: lineData) as? [String: Any],
                              let type = obj["type"] as? String else { continue }

                        switch type {
                        case "system":
                            if (obj["subtype"] as? String) == "init",
                               let sid = obj["session_id"] as? String {
                                capturedSessionID = sid
                            }
                        case "assistant":
                            guard let message = obj["message"] as? [String: Any],
                                  let content = message["content"] as? [[String: Any]] else { continue }
                            for block in content {
                                switch block["type"] as? String {
                                case "text":
                                    if let t = block["text"] as? String, !t.isEmpty {
                                        finalText += t
                                        let snapshot = finalText
                                        Task { @MainActor in onDelta(snapshot) }
                                    }
                                case "tool_use":
                                    guard let id = block["id"] as? String,
                                          let name = block["name"] as? String else { continue }
                                    let input = block["input"] as? [String: Any] ?? [:]
                                    let call = ToolCall(tool: name, detail: Self.describeInput(input),
                                                        status: .running, cliID: id)
                                    Task { @MainActor in onToolEvent(call) }
                                default: break
                                }
                            }
                        case "user":
                            guard let message = obj["message"] as? [String: Any],
                                  let content = message["content"] as? [[String: Any]] else { continue }
                            for block in content where block["type"] as? String == "tool_result" {
                                guard let id = block["tool_use_id"] as? String else { continue }
                                let isError = block["is_error"] as? Bool ?? false
                                let call = ToolCall(tool: "", detail: "",
                                                    status: isError ? .failed : .completed, cliID: id)
                                Task { @MainActor in onToolEvent(call) }
                            }
                        case "result":
                            gotResult = true
                            if let result = obj["result"] as? String, finalText.isEmpty {
                                finalText = result
                            }
                        default:
                            break
                        }
                    }
                }
            }

            stderr.fileHandleForReading.readabilityHandler = { handle in
                let data = handle.availableData
                guard !data.isEmpty else { return }
                let chunk = String(data: data, encoding: .utf8) ?? ""
                parseQueue.async { errText += chunk }
            }

            process.terminationHandler = { proc in
                stdout.fileHandleForReading.readabilityHandler = nil
                stderr.fileHandleForReading.readabilityHandler = nil
                parseQueue.async {
                    if let sid = capturedSessionID {
                        Task { @MainActor [weak self] in self?.sessionID = sid }
                    }
                    if proc.terminationStatus != 0 && !gotResult {
                        // An invalid/expired --resume id is a common cause of
                        // a non-zero exit here — drop it so the *next* turn
                        // starts a fresh session instead of failing forever.
                        if errText.localizedCaseInsensitiveContains("session") {
                            Task { @MainActor [weak self] in self?.sessionID = "" }
                        }
                        let msg = errText.isEmpty
                            ? "claude exited with status \(proc.terminationStatus)"
                            : errText
                        continuation.resume(throwing: NSError(
                            domain: "ClaudeCLI", code: Int(proc.terminationStatus),
                            userInfo: [NSLocalizedDescriptionKey: msg]))
                    } else {
                        continuation.resume(returning: .init(role: "assistant", content: finalText,
                                                             tool_calls: nil, tool_call_id: nil))
                    }
                }
            }

            do {
                try process.run()
            } catch {
                continuation.resume(throwing: error)
            }
        }
    }

    private static func describeInput(_ input: [String: Any]) -> String {
        for key in ["command", "file_path", "path", "url", "query", "pattern", "prompt"] {
            if let v = input[key] as? String { return v }
        }
        return ""
    }
}
