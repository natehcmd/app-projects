import Foundation

@MainActor
final class AgentRunner: ObservableObject {
    @Published var output: String = ""
    @Published var isRunning = false
    @Published var statusMessage = "Ready — I can watch, listen, download, convert, and search the web."

    private var process: Process?

    /// Folder where the agent works and where results land.
    let workspace: URL = {
        let url = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("AgentDrop-Workspace")
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }()

    private func findClaude() -> String? {
        let candidates = [
            NSHomeDirectory() + "/.npm-global/bin/claude",
            "/opt/homebrew/bin/claude",
            "/usr/local/bin/claude",
        ]
        return candidates.first { FileManager.default.isExecutableFile(atPath: $0) }
    }

    func run(instruction: String, files: [URL]) {
        guard !isRunning else { return }
        guard let claudePath = findClaude() else {
            output += "❌ Couldn't find the claude CLI. Install it with:\n  npm install -g @anthropic-ai/claude-code\n"
            return
        }

        var prompt = instruction
        let localFiles = files.filter { $0.isFileURL }
        let links = files.filter { !$0.isFileURL }
        if !localFiles.isEmpty {
            prompt += "\n\nAttached file(s):\n" + localFiles.map { "- \($0.path)" }.joined(separator: "\n")
        }
        if !links.isEmpty {
            prompt += "\n\nAttached link(s):\n" + links.map { "- \($0.absoluteString)" }.joined(separator: "\n")
            prompt += "\nIf a link points to a video, yt-dlp is installed and available for downloading it."
        }
        if !files.isEmpty {
            prompt += "\n\nIf you produce any output files, save them to \(workspace.path) and state their full paths at the end."
        }

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: claudePath)
        proc.arguments = ["-p", prompt, "--dangerously-skip-permissions", "--verbose", "--output-format", "stream-json"]
        proc.currentDirectoryURL = workspace

        var env = ProcessInfo.processInfo.environment
        let extraPaths = [
            NSHomeDirectory() + "/.npm-global/bin",
            "/opt/homebrew/bin",
            "/usr/local/bin",
            "/usr/bin", "/bin", "/usr/sbin", "/sbin",
        ]
        env["PATH"] = extraPaths.joined(separator: ":") + ":" + (env["PATH"] ?? "")
        proc.environment = env

        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = pipe

        var lineBuffer = ""
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
            Task { @MainActor in
                guard let self else { return }
                lineBuffer += text
                while let newline = lineBuffer.firstIndex(of: "\n") {
                    let line = String(lineBuffer[..<newline])
                    lineBuffer = String(lineBuffer[lineBuffer.index(after: newline)...])
                    if let rendered = Self.renderStreamLine(line) {
                        self.output += rendered
                    }
                }
            }
        }

        proc.terminationHandler = { [weak self] p in
            Task { @MainActor in
                guard let self else { return }
                pipe.fileHandleForReading.readabilityHandler = nil
                self.isRunning = false
                self.process = nil
                self.statusMessage = p.terminationStatus == 0
                    ? "✅ Done. Output files (if any) are in ~/AgentDrop-Workspace"
                    : "⚠️ Agent exited with status \(p.terminationStatus)"
            }
        }

        output = ""
        statusMessage = "🤖 Working on it…"
        isRunning = true
        do {
            try proc.run()
            process = proc
        } catch {
            isRunning = false
            output += "❌ Failed to launch agent: \(error.localizedDescription)\n"
            statusMessage = "Ready."
        }
    }

    /// Turns one stream-json line from the claude CLI into user-friendly text.
    nonisolated static func renderStreamLine(_ line: String) -> String? {
        guard let data = line.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String else {
            return line.isEmpty ? nil : line + "\n"
        }

        switch type {
        case "system":
            return (json["subtype"] as? String) == "init" ? "🚀 Agent started…\n\n" : nil
        case "assistant":
            guard let message = json["message"] as? [String: Any],
                  let content = message["content"] as? [[String: Any]] else { return nil }
            var out = ""
            for block in content {
                switch block["type"] as? String {
                case "text":
                    if let text = block["text"] as? String, !text.isEmpty {
                        out += text + "\n"
                    }
                case "tool_use":
                    let name = block["name"] as? String ?? "tool"
                    var detail = ""
                    if let input = block["input"] as? [String: Any] {
                        detail = (input["description"] as? String)
                            ?? (input["file_path"] as? String)
                            ?? (input["command"] as? String).map { String($0.prefix(80)) }
                            ?? (input["pattern"] as? String)
                            ?? ""
                    }
                    out += "  🔧 \(name)\(detail.isEmpty ? "" : ": \(detail)")\n"
                default:
                    break
                }
            }
            return out.isEmpty ? nil : out
        case "result":
            var out = "\n─────────────\n"
            if let result = json["result"] as? String, !result.isEmpty {
                out += result + "\n"
            }
            return out
        default:
            return nil
        }
    }

    func stop() {
        process?.terminate()
        statusMessage = "⏹ Stopped."
    }
}
