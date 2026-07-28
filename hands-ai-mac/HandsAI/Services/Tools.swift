import Foundation
import AppKit

/// Registry of tools the local agent can call via Ollama's function-calling API.
/// Each tool has a JSON schema spec (sent to the model) and an executor
/// (invoked when the model emits a tool_call for that name).
@MainActor
struct Tools {
    typealias Spec = OllamaClient.ToolSpec
    typealias Args = OllamaClient.ArgsJSON

    /// Set at launch so use_skill / list_skills can reach the skill library.
    static weak var skills: SkillsStore?

    static let all: [Spec] = [
        readFileSpec, listDirSpec, writeFileSpec, runBashSpec, getStatsSpec,
        openAppSpec, listAppsSpec, runAppleScriptSpec, openURLSpec,
        webFetchSpec, webSearchSpec, notifySpec,
        clipboardReadSpec, clipboardWriteSpec,
        useSkillSpec, listSkillsSpec,
    ] + macSpecs

    static func run(toolCall: OllamaClient.ToolCallReq) async -> String {
        let name = toolCall.function.name
        let args = toolCall.function.arguments
        do {
            switch name {
            case "read_file":       return try readFile(args: args)
            case "list_dir":        return try listDir(args: args)
            case "write_file":      return try writeFile(args: args)
            case "run_bash":        return try await runBash(args: args)
            case "get_stats":       return try getStats(args: args)
            case "open_app":        return openApp(args: args)
            case "list_apps":       return listApps(args: args)
            case "run_applescript": return try await runAppleScript(args: args)
            case "open_url":        return openURL(args: args)
            case "web_fetch":       return try await webFetch(args: args)
            case "web_search":      return try await webSearch(args: args)
            case "notify":          return try await notify(args: args)
            case "clipboard_read":  return clipboardRead(args: args)
            case "clipboard_write": return clipboardWrite(args: args)
            case "use_skill":       return useSkill(args: args)
            case "list_skills":     return listSkills(args: args)
            default:
                if let result = await runMac(name: name, args: args) { return result }
                return "error: unknown tool \(name)"
            }
        } catch {
            return "error: \(error.localizedDescription)"
        }
    }

    // MARK: - Specs (advertised to the model)

    static let readFileSpec = Spec(function: .init(
        name: "read_file",
        description: "Read the contents of a file from the local filesystem.",
        parameters: .init(properties: [
            "path": .init(type: "string", description: "Absolute or ~-relative path to the file."),
        ], required: ["path"])
    ))

    static let listDirSpec = Spec(function: .init(
        name: "list_dir",
        description: "List entries in a directory (non-recursive).",
        parameters: .init(properties: [
            "path": .init(type: "string", description: "Absolute or ~-relative directory path."),
        ], required: ["path"])
    ))

    static let writeFileSpec = Spec(function: .init(
        name: "write_file",
        description: "Create or overwrite a text file with the given contents.",
        parameters: .init(properties: [
            "path":    .init(type: "string", description: "Absolute or ~-relative path."),
            "content": .init(type: "string", description: "The full file contents to write."),
        ], required: ["path", "content"])
    ))

    static let runBashSpec = Spec(function: .init(
        name: "run_bash",
        description: "Execute a shell command via /bin/bash -c and return its combined stdout+stderr. Use for git, ls, grep, system queries, etc. Output is truncated to 4000 characters.",
        parameters: .init(properties: [
            "command": .init(type: "string", description: "The shell command to run."),
        ], required: ["command"])
    ))

    static let getStatsSpec = Spec(function: .init(
        name: "get_stats",
        description: "Return a snapshot of current system stats: CPU %, RAM used, disk free, uptime.",
        parameters: .init(properties: [:], required: [])
    ))

    static let openAppSpec = Spec(function: .init(
        name: "open_app",
        description: "Launch or bring to front a Mac application by name, e.g. 'Safari', 'Notes', 'Visual Studio Code'. Use list_apps if unsure of the exact name.",
        parameters: .init(properties: [
            "name": .init(type: "string", description: "The application name as it appears in /Applications."),
        ], required: ["name"])
    ))

    static let listAppsSpec = Spec(function: .init(
        name: "list_apps",
        description: "List installed applications (from /Applications and /System/Applications) plus currently running apps.",
        parameters: .init(properties: [:], required: [])
    ))

    static let runAppleScriptSpec = Spec(function: .init(
        name: "run_applescript",
        description: "Run an AppleScript via osascript and return its output. This can control almost every Mac app: Calendar, Notes, Reminders, Mail, Messages, Music, Safari, Finder, System Events. Example: tell application \"Music\" to playpause",
        parameters: .init(properties: [
            "script": .init(type: "string", description: "The AppleScript source to execute."),
        ], required: ["script"])
    ))

    static let openURLSpec = Spec(function: .init(
        name: "open_url",
        description: "Open a URL in the user's default browser (or the app registered for the scheme).",
        parameters: .init(properties: [
            "url": .init(type: "string", description: "Full URL including scheme, e.g. https://github.com"),
        ], required: ["url"])
    ))

    static let webFetchSpec = Spec(function: .init(
        name: "web_fetch",
        description: "Fetch a web page and return its readable text content (HTML stripped, truncated to ~6000 chars). Use for reading articles, docs, or API responses.",
        parameters: .init(properties: [
            "url": .init(type: "string", description: "Full https URL to fetch."),
        ], required: ["url"])
    ))

    static let webSearchSpec = Spec(function: .init(
        name: "web_search",
        description: "Search the web (DuckDuckGo) and return the top results as title, URL, and snippet. Use for anything current: news, prices, versions, docs.",
        parameters: .init(properties: [
            "query": .init(type: "string", description: "The search query."),
        ], required: ["query"])
    ))

    static let notifySpec = Spec(function: .init(
        name: "notify",
        description: "Post a macOS notification banner to the user.",
        parameters: .init(properties: [
            "title":   .init(type: "string", description: "Notification title."),
            "message": .init(type: "string", description: "Notification body text."),
        ], required: ["title", "message"])
    ))

    static let clipboardReadSpec = Spec(function: .init(
        name: "clipboard_read",
        description: "Read the current text contents of the macOS clipboard.",
        parameters: .init(properties: [:], required: [])
    ))

    static let clipboardWriteSpec = Spec(function: .init(
        name: "clipboard_write",
        description: "Replace the macOS clipboard with the given text.",
        parameters: .init(properties: [
            "text": .init(type: "string", description: "Text to place on the clipboard."),
        ], required: ["text"])
    ))

    static let useSkillSpec = Spec(function: .init(
        name: "use_skill",
        description: "Load a skill's full playbook by name. Skills are step-by-step procedures listed in your system prompt. Call this FIRST when a request matches a skill, then follow the returned steps.",
        parameters: .init(properties: [
            "name": .init(type: "string", description: "Skill slug or name, e.g. 'daily-briefing'."),
        ], required: ["name"])
    ))

    static let listSkillsSpec = Spec(function: .init(
        name: "list_skills",
        description: "List all installed skills with their descriptions (reloads from ~/hands-ai-skills first).",
        parameters: .init(properties: [:], required: [])
    ))

    // MARK: - Executors

    private static func expandPath(_ p: String) -> String {
        (p as NSString).expandingTildeInPath
    }

    static func readFile(args: Args) throws -> String {
        guard let raw = args.string("path") else { return "error: missing 'path'" }
        let path = expandPath(raw)
        let url = URL(fileURLWithPath: path)
        let attrs = try FileManager.default.attributesOfItem(atPath: path)
        let size = (attrs[.size] as? Int) ?? 0
        if size > 1_000_000 {
            return "error: file is \(size / 1024) KB, refusing to read >1 MB. Use run_bash with head/grep."
        }
        let data = try Data(contentsOf: url)
        return String(data: data, encoding: .utf8)
            ?? "(\(data.count) bytes binary — not displayed)"
    }

    static func listDir(args: Args) throws -> String {
        guard let raw = args.string("path") else { return "error: missing 'path'" }
        let path = expandPath(raw)
        let entries = try FileManager.default.contentsOfDirectory(atPath: path)
        let sorted = entries.sorted()
        let annotated = sorted.map { name -> String in
            let full = (path as NSString).appendingPathComponent(name)
            var isDir: ObjCBool = false
            FileManager.default.fileExists(atPath: full, isDirectory: &isDir)
            return isDir.boolValue ? "\(name)/" : name
        }
        return annotated.joined(separator: "\n")
    }

    static func writeFile(args: Args) throws -> String {
        guard let raw = args.string("path") else { return "error: missing 'path'" }
        guard let content = args.string("content") else { return "error: missing 'content'" }
        let path = expandPath(raw)
        let url = URL(fileURLWithPath: path)
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(),
                                                withIntermediateDirectories: true)
        try content.write(to: url, atomically: true, encoding: .utf8)
        return "wrote \(content.utf8.count) bytes to \(path)"
    }

    static func runBash(args: Args) async throws -> String {
        guard let command = args.string("command") else { return "error: missing 'command'" }
        let proc = Process()
        proc.launchPath = "/bin/bash"
        proc.arguments = ["-c", command]
        let outPipe = Pipe()
        proc.standardOutput = outPipe
        proc.standardError = outPipe
        try proc.run()
        proc.waitUntilExit()
        let data = outPipe.fileHandleForReading.readDataToEndOfFile()
        var out = String(data: data, encoding: .utf8) ?? "(binary output)"
        if out.utf8.count > 4000 {
            let end = out.index(out.startIndex, offsetBy: 4000)
            out = String(out[..<end]) + "\n…(truncated)"
        }
        let exit = proc.terminationStatus
        return "$ \(command)\n\(out)\n(exit \(exit))"
    }

    static func getStats(args: Args) throws -> String {
        var info = vm_statistics64_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<vm_statistics64_data_t>.size / MemoryLayout<integer_t>.size)
        let _ = withUnsafeMutablePointer(to: &info) { ptr -> kern_return_t in
            ptr.withMemoryRebound(to: integer_t.self, capacity: Int(count)) { intPtr in
                host_statistics64(mach_host_self(), HOST_VM_INFO64, intPtr, &count)
            }
        }
        var totalBytes: UInt64 = 0
        var sz = MemoryLayout<UInt64>.size
        sysctlbyname("hw.memsize", &totalBytes, &sz, nil, 0)
        let pageSize = UInt64(vm_kernel_page_size)
        let used = (UInt64(info.active_count) + UInt64(info.wire_count) + UInt64(info.compressor_page_count)) * pageSize
        let usedGB = Double(used) / 1_073_741_824.0
        let totalGB = Double(totalBytes) / 1_073_741_824.0

        let diskAttrs = try? FileManager.default.attributesOfFileSystem(forPath: "/")
        let diskFreeGB = ((diskAttrs?[.systemFreeSize] as? NSNumber)?.doubleValue ?? 0) / 1_073_741_824.0
        let diskTotalGB = ((diskAttrs?[.systemSize] as? NSNumber)?.doubleValue ?? 0) / 1_073_741_824.0

        return """
        RAM: \(String(format: "%.1f", usedGB)) / \(String(format: "%.0f", totalGB)) GB
        Disk: \(String(format: "%.0f", diskFreeGB)) GB free of \(String(format: "%.0f", diskTotalGB)) GB
        Thermal: \(ProcessInfo.processInfo.thermalState == .nominal ? "Nominal" : "Elevated")
        Host: \(Host.current().localizedName ?? "Mac")
        OS: \(ProcessInfo.processInfo.operatingSystemVersionString)
        """
    }

    // MARK: - App control

    static func openApp(args: Args) -> String {
        guard let name = args.string("name") else { return "error: missing 'name'" }
        let candidates = [
            "/Applications/\(name).app",
            "/System/Applications/\(name).app",
            "\(NSHomeDirectory())/Applications/\(name).app",
        ]
        if let path = candidates.first(where: { FileManager.default.fileExists(atPath: $0) }) {
            NSWorkspace.shared.openApplication(at: URL(fileURLWithPath: path),
                                               configuration: NSWorkspace.OpenConfiguration())
            return "opened \(name)"
        }
        // Fall back to Launch Services fuzzy lookup via `open -a`.
        let proc = Process()
        proc.launchPath = "/usr/bin/open"
        proc.arguments = ["-a", name]
        let pipe = Pipe()
        proc.standardError = pipe
        try? proc.run()
        proc.waitUntilExit()
        if proc.terminationStatus == 0 { return "opened \(name)" }
        let err = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        return "error: could not open '\(name)'. \(err.trimmingCharacters(in: .whitespacesAndNewlines)) Try list_apps for exact names."
    }

    static func listApps(args: Args) -> String {
        let fm = FileManager.default
        var installed = Set<String>()
        for dir in ["/Applications", "/System/Applications"] {
            for entry in (try? fm.contentsOfDirectory(atPath: dir)) ?? [] where entry.hasSuffix(".app") {
                installed.insert(String(entry.dropLast(4)))
            }
        }
        let running = NSWorkspace.shared.runningApplications
            .filter { $0.activationPolicy == .regular }
            .compactMap { $0.localizedName }
            .sorted()
        return """
        Running: \(running.joined(separator: ", "))

        Installed:
        \(installed.sorted().joined(separator: "\n"))
        """
    }

    static func runAppleScript(args: Args) async throws -> String {
        guard let script = args.string("script") else { return "error: missing 'script'" }
        let proc = Process()
        proc.launchPath = "/usr/bin/osascript"
        proc.arguments = ["-e", script]
        let outPipe = Pipe()
        proc.standardOutput = outPipe
        proc.standardError = outPipe
        try proc.run()
        proc.waitUntilExit()
        var out = String(data: outPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        out = out.trimmingCharacters(in: .whitespacesAndNewlines)
        if out.utf8.count > 4000 { out = String(out.prefix(4000)) + "…(truncated)" }
        if proc.terminationStatus != 0 {
            return "error: applescript failed — \(out)"
        }
        return out.isEmpty ? "(ok, no output)" : out
    }

    static func openURL(args: Args) -> String {
        guard let raw = args.string("url"), let url = URL(string: raw) else {
            return "error: missing or invalid 'url'"
        }
        NSWorkspace.shared.open(url)
        return "opened \(raw)"
    }

    // MARK: - Web

    private static let webSession: URLSession = {
        let cfg = URLSessionConfiguration.ephemeral
        cfg.timeoutIntervalForRequest = 20
        return URLSession(configuration: cfg)
    }()

    static func webFetch(args: Args) async throws -> String {
        guard let raw = args.string("url"), let url = URL(string: raw) else {
            return "error: missing or invalid 'url'"
        }
        var req = URLRequest(url: url)
        req.setValue("Mozilla/5.0 (Macintosh) HandsAI/0.3", forHTTPHeaderField: "User-Agent")
        let (data, response) = try await webSession.data(for: req)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard status == 200 else { return "error: HTTP \(status) from \(raw)" }
        let html = String(data: data, encoding: .utf8) ?? ""
        let text = stripHTML(html)
        let trimmed = text.count > 6000 ? String(text.prefix(6000)) + "…(truncated)" : text
        return trimmed.isEmpty ? "(page had no readable text)" : trimmed
    }

    static func webSearch(args: Args) async throws -> String {
        guard let query = args.string("query") else { return "error: missing 'query'" }
        let q = query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? query
        guard let url = URL(string: "https://html.duckduckgo.com/html/?q=\(q)") else {
            return "error: bad query"
        }
        var req = URLRequest(url: url)
        req.setValue("Mozilla/5.0 (Macintosh) HandsAI/0.3", forHTTPHeaderField: "User-Agent")
        let (data, _) = try await webSession.data(for: req)
        let html = String(data: data, encoding: .utf8) ?? ""

        // Results look like: <a rel="nofollow" class="result__a" href="URL">TITLE</a>
        // ... <a class="result__snippet" ...>SNIPPET</a>
        var results: [String] = []
        let linkPattern = #"class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>"#
        let snippetPattern = #"class="result__snippet"[^>]*>(.*?)</a>"#
        let links = matches(pattern: linkPattern, in: html)
        let snippets = matches(pattern: snippetPattern, in: html)
        for (i, link) in links.prefix(6).enumerated() {
            let rawURL = decodeDuckURL(link[0])
            let title = stripHTML(link[1])
            let snippet = i < snippets.count ? stripHTML(snippets[i][0]) : ""
            results.append("\(i + 1). \(title)\n   \(rawURL)\n   \(snippet)")
        }
        return results.isEmpty
            ? "no results found for '\(query)'"
            : results.joined(separator: "\n\n")
    }

    /// DuckDuckGo wraps result URLs as //duckduckgo.com/l/?uddg=<encoded>&…
    private static func decodeDuckURL(_ href: String) -> String {
        if let range = href.range(of: "uddg=") {
            let tail = String(href[range.upperBound...])
            let encoded = tail.split(separator: "&").first.map(String.init) ?? tail
            return encoded.removingPercentEncoding ?? href
        }
        return href
    }

    private static func matches(pattern: String, in text: String) -> [[String]] {
        guard let re = try? NSRegularExpression(pattern: pattern,
                                                options: [.dotMatchesLineSeparators]) else { return [] }
        let ns = text as NSString
        return re.matches(in: text, range: NSRange(location: 0, length: ns.length)).map { m in
            (1..<m.numberOfRanges).compactMap { i in
                m.range(at: i).location == NSNotFound ? nil : ns.substring(with: m.range(at: i))
            }
        }
    }

    private static func stripHTML(_ html: String) -> String {
        var s = html
        // Drop script/style blocks entirely, then tags, then collapse whitespace.
        for block in ["script", "style", "noscript", "svg", "head"] {
            s = s.replacingOccurrences(of: "<\(block)[\\s\\S]*?</\(block)>",
                                       with: " ", options: [.regularExpression, .caseInsensitive])
        }
        s = s.replacingOccurrences(of: "<[^>]+>", with: " ", options: .regularExpression)
        s = s.replacingOccurrences(of: "&amp;", with: "&")
            .replacingOccurrences(of: "&lt;", with: "<")
            .replacingOccurrences(of: "&gt;", with: ">")
            .replacingOccurrences(of: "&quot;", with: "\"")
            .replacingOccurrences(of: "&#x27;", with: "'")
            .replacingOccurrences(of: "&#39;", with: "'")
            .replacingOccurrences(of: "&nbsp;", with: " ")
        s = s.replacingOccurrences(of: "[ \\t]+", with: " ", options: .regularExpression)
        s = s.replacingOccurrences(of: "\\s*\\n\\s*", with: "\n", options: .regularExpression)
        return s.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    // MARK: - Notifications & clipboard

    static func notify(args: Args) async throws -> String {
        guard let title = args.string("title"), let message = args.string("message") else {
            return "error: missing 'title' or 'message'"
        }
        func esc(_ s: String) -> String {
            s.replacingOccurrences(of: "\\", with: "\\\\")
             .replacingOccurrences(of: "\"", with: "\\\"")
        }
        let script = "display notification \"\(esc(message))\" with title \"\(esc(title))\""
        let proc = Process()
        proc.launchPath = "/usr/bin/osascript"
        proc.arguments = ["-e", script]
        try proc.run()
        proc.waitUntilExit()
        return proc.terminationStatus == 0 ? "notification posted" : "error: notification failed"
    }

    static func clipboardRead(args: Args) -> String {
        NSPasteboard.general.string(forType: .string) ?? "(clipboard is empty or non-text)"
    }

    static func clipboardWrite(args: Args) -> String {
        guard let text = args.string("text") else { return "error: missing 'text'" }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
        return "clipboard set (\(text.count) chars)"
    }

    // MARK: - Skills

    static func useSkill(args: Args) -> String {
        guard let name = args.string("name") else { return "error: missing 'name'" }
        guard let store = skills else { return "error: skill library unavailable" }
        guard let skill = store.skill(named: name) else {
            return "error: no skill named '\(name)'. Installed:\n\(store.promptSummary)"
        }
        return skill.body
    }

    static func listSkills(args: Args) -> String {
        guard let store = skills else { return "error: skill library unavailable" }
        store.reload()
        return store.skills.isEmpty
            ? "no skills installed. Add markdown files to ~/hands-ai-skills/"
            : store.promptSummary
    }
}
