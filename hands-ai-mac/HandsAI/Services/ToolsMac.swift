import Foundation
import AppKit

/// Second wave of capabilities: deeper macOS integration — files, Spotlight,
/// Calendar/Reminders/Notes/Messages, Music, volume, screenshots, Shortcuts,
/// timers, weather, calculator, system actions. Registered in Tools.all.
extension Tools {

    // MARK: - Shared helpers

    static func osascript(_ script: String) -> (out: String, ok: Bool) {
        let proc = Process()
        proc.launchPath = "/usr/bin/osascript"
        proc.arguments = ["-e", script]
        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = pipe
        do { try proc.run() } catch { return ("error: \(error.localizedDescription)", false) }
        proc.waitUntilExit()
        var out = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        out = out.trimmingCharacters(in: .whitespacesAndNewlines)
        if out.utf8.count > 4000 { out = String(out.prefix(4000)) + "…(truncated)" }
        return (out, proc.terminationStatus == 0)
    }

    static func shell(_ launchPath: String, _ args: [String]) -> (out: String, ok: Bool) {
        let proc = Process()
        proc.launchPath = launchPath
        proc.arguments = args
        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = pipe
        do { try proc.run() } catch { return ("error: \(error.localizedDescription)", false) }
        proc.waitUntilExit()
        var out = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        out = out.trimmingCharacters(in: .whitespacesAndNewlines)
        if out.utf8.count > 4000 { out = String(out.prefix(4000)) + "…(truncated)" }
        return (out, proc.terminationStatus == 0)
    }

    static func escAS(_ s: String) -> String {
        s.replacingOccurrences(of: "\\", with: "\\\\")
         .replacingOccurrences(of: "\"", with: "\\\"")
    }

    // MARK: - Specs

    static let macSpecs: [Spec] = [
        Spec(function: .init(
            name: "search_files",
            description: "Search the whole Mac by file name or metadata using Spotlight. Returns up to 20 matching paths.",
            parameters: .init(properties: [
                "query": .init(type: "string", description: "File name or phrase to search for."),
            ], required: ["query"])
        )),
        Spec(function: .init(
            name: "search_file_contents",
            description: "Search inside text files under a directory for a string (recursive grep). Returns matching file:line snippets.",
            parameters: .init(properties: [
                "text": .init(type: "string", description: "The text to find."),
                "path": .init(type: "string", description: "Directory to search, ~-relative ok. Default ~."),
            ], required: ["text"])
        )),
        Spec(function: .init(
            name: "open_file",
            description: "Open a file or folder in its default app (or reveal a folder in Finder).",
            parameters: .init(properties: [
                "path": .init(type: "string", description: "Absolute or ~-relative path."),
            ], required: ["path"])
        )),
        Spec(function: .init(
            name: "move_file",
            description: "Move or rename a file/folder.",
            parameters: .init(properties: [
                "from": .init(type: "string", description: "Source path."),
                "to":   .init(type: "string", description: "Destination path."),
            ], required: ["from", "to"])
        )),
        Spec(function: .init(
            name: "copy_file",
            description: "Copy a file/folder.",
            parameters: .init(properties: [
                "from": .init(type: "string", description: "Source path."),
                "to":   .init(type: "string", description: "Destination path."),
            ], required: ["from", "to"])
        )),
        Spec(function: .init(
            name: "trash_file",
            description: "Move a file or folder to the Trash (recoverable — safer than rm).",
            parameters: .init(properties: [
                "path": .init(type: "string", description: "Path to trash."),
            ], required: ["path"])
        )),
        Spec(function: .init(
            name: "screenshot",
            description: "Capture the full screen to a PNG on the Desktop and return its path.",
            parameters: .init(properties: [:], required: [])
        )),
        Spec(function: .init(
            name: "calendar_today",
            description: "List today's and tomorrow's calendar events (title, start time, calendar).",
            parameters: .init(properties: [:], required: [])
        )),
        Spec(function: .init(
            name: "calendar_add_event",
            description: "Create a calendar event. Times are 24h local, e.g. '2026-07-08 14:30'.",
            parameters: .init(properties: [
                "title": .init(type: "string", description: "Event title."),
                "start": .init(type: "string", description: "Start: 'YYYY-MM-DD HH:MM'."),
                "end":   .init(type: "string", description: "End: 'YYYY-MM-DD HH:MM'. Default 1 hour after start."),
            ], required: ["title", "start"])
        )),
        Spec(function: .init(
            name: "reminders_add",
            description: "Add a reminder to Apple Reminders, optionally with a due date.",
            parameters: .init(properties: [
                "title": .init(type: "string", description: "Reminder text."),
                "due":   .init(type: "string", description: "Optional due 'YYYY-MM-DD HH:MM'."),
            ], required: ["title"])
        )),
        Spec(function: .init(
            name: "reminders_list",
            description: "List incomplete reminders from the default list.",
            parameters: .init(properties: [:], required: [])
        )),
        Spec(function: .init(
            name: "add_note",
            description: "Create a note in Apple Notes.",
            parameters: .init(properties: [
                "title": .init(type: "string", description: "Note title."),
                "body":  .init(type: "string", description: "Note body text."),
            ], required: ["title", "body"])
        )),
        Spec(function: .init(
            name: "send_imessage",
            description: "Send an iMessage. ONLY use when the user explicitly asked to send a message in this conversation, and confirm recipient + text first if there is any ambiguity.",
            parameters: .init(properties: [
                "to":   .init(type: "string", description: "Recipient phone number or iMessage email."),
                "text": .init(type: "string", description: "The message to send."),
            ], required: ["to", "text"])
        )),
        Spec(function: .init(
            name: "music",
            description: "Control Apple Music: action is one of play, pause, toggle, next, previous, current (returns now-playing info), or play_playlist with 'name'.",
            parameters: .init(properties: [
                "action": .init(type: "string", description: "play | pause | toggle | next | previous | current | play_playlist"),
                "name":   .init(type: "string", description: "Playlist name (play_playlist only)."),
            ], required: ["action"])
        )),
        Spec(function: .init(
            name: "set_volume",
            description: "Set system output volume 0-100, or pass 'mute' / 'unmute'.",
            parameters: .init(properties: [
                "level": .init(type: "string", description: "0-100, 'mute', or 'unmute'."),
            ], required: ["level"])
        )),
        Spec(function: .init(
            name: "run_shortcut",
            description: "Run a macOS Shortcuts shortcut by name (optionally with text input) and return its output. Very powerful — use list_shortcuts to see what's available.",
            parameters: .init(properties: [
                "name":  .init(type: "string", description: "Exact shortcut name."),
                "input": .init(type: "string", description: "Optional text input passed to the shortcut."),
            ], required: ["name"])
        )),
        Spec(function: .init(
            name: "list_shortcuts",
            description: "List all macOS Shortcuts available to run.",
            parameters: .init(properties: [:], required: [])
        )),
        Spec(function: .init(
            name: "timer_set",
            description: "Set a timer: after N minutes, post a notification (and it appears in the tool feed).",
            parameters: .init(properties: [
                "minutes": .init(type: "string", description: "Minutes from now (can be fractional, e.g. 0.5)."),
                "message": .init(type: "string", description: "What to say when time is up."),
            ], required: ["minutes", "message"])
        )),
        Spec(function: .init(
            name: "weather",
            description: "Current weather one-liner for a location (default: current IP location).",
            parameters: .init(properties: [
                "location": .init(type: "string", description: "City name, optional."),
            ], required: [])
        )),
        Spec(function: .init(
            name: "calculate",
            description: "Evaluate an arithmetic expression precisely (uses bc: + - * / ^ parentheses, sqrt(), decimals).",
            parameters: .init(properties: [
                "expression": .init(type: "string", description: "e.g. (2^10 + 24) / 7"),
            ], required: ["expression"])
        )),
        Spec(function: .init(
            name: "frontmost_app",
            description: "Return the app the user is currently using and its frontmost window title.",
            parameters: .init(properties: [:], required: [])
        )),
        Spec(function: .init(
            name: "system_action",
            description: "Perform a system action: lock (lock screen), sleep (sleep displays), dark_mode (toggle), do_not_disturb (toggle Focus via Shortcuts if a 'Toggle DND' shortcut exists), empty_trash (ASK the user first).",
            parameters: .init(properties: [
                "action": .init(type: "string", description: "lock | sleep | dark_mode | empty_trash"),
            ], required: ["action"])
        )),
    ]

    // MARK: - Dispatch

    static func runMac(name: String, args: Args) async -> String? {
        switch name {
        case "search_files":          return searchFiles(args: args)
        case "search_file_contents":  return searchFileContents(args: args)
        case "open_file":             return openFile(args: args)
        case "move_file":             return moveFile(args: args)
        case "copy_file":             return copyFile(args: args)
        case "trash_file":            return trashFile(args: args)
        case "screenshot":            return screenshot(args: args)
        case "calendar_today":        return calendarToday()
        case "calendar_add_event":    return calendarAddEvent(args: args)
        case "reminders_add":         return remindersAdd(args: args)
        case "reminders_list":        return remindersList()
        case "add_note":              return addNote(args: args)
        case "send_imessage":         return sendIMessage(args: args)
        case "music":                 return music(args: args)
        case "set_volume":            return setVolume(args: args)
        case "run_shortcut":          return runShortcut(args: args)
        case "list_shortcuts":        return listShortcuts()
        case "timer_set":             return timerSet(args: args)
        case "weather":               return await weather(args: args)
        case "calculate":             return calculate(args: args)
        case "frontmost_app":         return frontmostApp()
        case "system_action":         return systemAction(args: args)
        default:                      return nil
        }
    }

    // MARK: - Files & search

    private static func expand(_ p: String) -> String { (p as NSString).expandingTildeInPath }

    static func searchFiles(args: Args) -> String {
        guard let q = args.string("query") else { return "error: missing 'query'" }
        let r = shell("/usr/bin/mdfind", ["-name", q])
        let lines = r.out.split(separator: "\n").prefix(20)
        return lines.isEmpty ? "no files matching '\(q)'" : lines.joined(separator: "\n")
    }

    static func searchFileContents(args: Args) -> String {
        guard let text = args.string("text") else { return "error: missing 'text'" }
        let dir = expand(args.string("path") ?? "~")
        let r = shell("/usr/bin/grep", ["-rIn", "--include=*", "-m", "3",
                                        "--exclude-dir=.git", "--exclude-dir=node_modules",
                                        "--exclude-dir=Library", text, dir])
        let lines = r.out.split(separator: "\n").prefix(20)
        return lines.isEmpty ? "no matches for '\(text)' under \(dir)" : lines.joined(separator: "\n")
    }

    static func openFile(args: Args) -> String {
        guard let raw = args.string("path") else { return "error: missing 'path'" }
        let path = expand(raw)
        guard FileManager.default.fileExists(atPath: path) else { return "error: no such path \(path)" }
        NSWorkspace.shared.open(URL(fileURLWithPath: path))
        return "opened \(path)"
    }

    static func moveFile(args: Args) -> String {
        guard let f = args.string("from"), let t = args.string("to") else { return "error: need 'from' and 'to'" }
        do {
            try FileManager.default.moveItem(atPath: expand(f), toPath: expand(t))
            return "moved \(f) → \(t)"
        } catch { return "error: \(error.localizedDescription)" }
    }

    static func copyFile(args: Args) -> String {
        guard let f = args.string("from"), let t = args.string("to") else { return "error: need 'from' and 'to'" }
        do {
            try FileManager.default.copyItem(atPath: expand(f), toPath: expand(t))
            return "copied \(f) → \(t)"
        } catch { return "error: \(error.localizedDescription)" }
    }

    static func trashFile(args: Args) -> String {
        guard let raw = args.string("path") else { return "error: missing 'path'" }
        do {
            var trashed: NSURL?
            try FileManager.default.trashItem(at: URL(fileURLWithPath: expand(raw)), resultingItemURL: &trashed)
            return "moved to Trash: \(raw)"
        } catch { return "error: \(error.localizedDescription)" }
    }

    static func screenshot(args: Args) -> String {
        let stamp = DateFormatter()
        stamp.dateFormat = "yyyy-MM-dd_HH-mm-ss"
        let path = expand("~/Desktop/hands-shot-\(stamp.string(from: Date())).png")
        let r = shell("/usr/sbin/screencapture", ["-x", path])
        if FileManager.default.fileExists(atPath: path) {
            return "screenshot saved to \(path)"
        }
        return "error: screenshot failed. \(r.out) (grant Screen Recording permission in System Settings → Privacy)"
    }

    // MARK: - Calendar / Reminders / Notes / Messages

    static func calendarToday() -> String {
        let script = """
        set out to ""
        tell application "Calendar"
            set d1 to (current date) - (time of (current date))
            set d2 to d1 + 2 * days
            repeat with cal in calendars
                set evs to (every event of cal whose start date ≥ d1 and start date < d2)
                repeat with ev in evs
                    set out to out & (start date of ev as string) & " — " & (summary of ev) & linefeed
                end repeat
            end repeat
        end tell
        return out
        """
        let r = osascript(script)
        if !r.ok { return "error: \(r.out) (grant Calendar access when prompted)" }
        return r.out.isEmpty ? "no events today or tomorrow" : r.out
    }

    static func calendarAddEvent(args: Args) -> String {
        guard let title = args.string("title"), let start = args.string("start") else {
            return "error: need 'title' and 'start'"
        }
        let fmt = DateFormatter()
        fmt.dateFormat = "yyyy-MM-dd HH:mm"
        guard let startDate = fmt.date(from: start) else { return "error: start must be 'YYYY-MM-DD HH:MM'" }
        let endDate = args.string("end").flatMap { fmt.date(from: $0) } ?? startDate.addingTimeInterval(3600)
        let asFmt = DateFormatter()
        asFmt.dateFormat = "MMMM d, yyyy HH:mm:ss"
        let script = """
        tell application "Calendar"
            tell first calendar whose writable is true
                make new event with properties {summary:"\(escAS(title))", start date:date "\(asFmt.string(from: startDate))", end date:date "\(asFmt.string(from: endDate))"}
            end tell
        end tell
        """
        let r = osascript(script)
        return r.ok ? "event '\(title)' created for \(start)" : "error: \(r.out)"
    }

    static func remindersAdd(args: Args) -> String {
        guard let title = args.string("title") else { return "error: missing 'title'" }
        var props = "name:\"\(escAS(title))\""
        if let due = args.string("due") {
            let fmt = DateFormatter(); fmt.dateFormat = "yyyy-MM-dd HH:mm"
            if let d = fmt.date(from: due) {
                let asFmt = DateFormatter(); asFmt.dateFormat = "MMMM d, yyyy HH:mm:ss"
                props += ", due date:date \"\(asFmt.string(from: d))\""
            }
        }
        let r = osascript("tell application \"Reminders\" to make new reminder with properties {\(props)}")
        return r.ok ? "reminder added: \(title)" : "error: \(r.out)"
    }

    static func remindersList() -> String {
        let r = osascript("""
        tell application "Reminders"
            set out to ""
            repeat with rem in (reminders of default list whose completed is false)
                set out to out & "- " & (name of rem) & linefeed
            end repeat
            return out
        end tell
        """)
        if !r.ok { return "error: \(r.out)" }
        return r.out.isEmpty ? "no open reminders" : r.out
    }

    static func addNote(args: Args) -> String {
        guard let title = args.string("title"), let body = args.string("body") else {
            return "error: need 'title' and 'body'"
        }
        let r = osascript("tell application \"Notes\" to make new note at folder \"Notes\" with properties {name:\"\(escAS(title))\", body:\"\(escAS(body))\"}")
        return r.ok ? "note '\(title)' created" : "error: \(r.out)"
    }

    static func sendIMessage(args: Args) -> String {
        guard let to = args.string("to"), let text = args.string("text") else {
            return "error: need 'to' and 'text'"
        }
        let r = osascript("""
        tell application "Messages"
            set svc to first account whose service type is iMessage
            send "\(escAS(text))" to participant "\(escAS(to))" of svc
        end tell
        """)
        return r.ok ? "iMessage sent to \(to)" : "error: \(r.out)"
    }

    // MARK: - Music / volume / system

    static func music(args: Args) -> String {
        let action = args.string("action") ?? "current"
        let script: String
        switch action {
        case "play":      script = "tell application \"Music\" to play"
        case "pause":     script = "tell application \"Music\" to pause"
        case "toggle":    script = "tell application \"Music\" to playpause"
        case "next":      script = "tell application \"Music\" to next track"
        case "previous":  script = "tell application \"Music\" to previous track"
        case "play_playlist":
            guard let name = args.string("name") else { return "error: play_playlist needs 'name'" }
            script = "tell application \"Music\" to play playlist \"\(escAS(name))\""
        case "current":
            script = """
            tell application "Music"
                if player state is playing then
                    return (name of current track) & " — " & (artist of current track) & " (" & (album of current track) & ")"
                else
                    return "nothing playing"
                end if
            end tell
            """
        default: return "error: unknown action '\(action)'"
        }
        let r = osascript(script)
        return r.ok ? (r.out.isEmpty ? "done (\(action))" : r.out) : "error: \(r.out)"
    }

    static func setVolume(args: Args) -> String {
        guard let level = args.string("level") else { return "error: missing 'level'" }
        let script: String
        if level == "mute" { script = "set volume output muted true" }
        else if level == "unmute" { script = "set volume output muted false" }
        else if let n = Int(level), (0...100).contains(n) { script = "set volume output volume \(n)" }
        else { return "error: level must be 0-100, 'mute', or 'unmute'" }
        let r = osascript(script)
        return r.ok ? "volume: \(level)" : "error: \(r.out)"
    }

    static func frontmostApp() -> String {
        let app = NSWorkspace.shared.frontmostApplication?.localizedName ?? "unknown"
        let r = osascript("""
        tell application "System Events"
            set p to first process whose frontmost is true
            try
                return name of front window of p
            on error
                return ""
            end try
        end tell
        """)
        let win = r.ok && !r.out.isEmpty ? " — window: \(r.out)" : ""
        return "frontmost app: \(app)\(win)"
    }

    static func systemAction(args: Args) -> String {
        let action = args.string("action") ?? ""
        switch action {
        case "lock":
            let r = shell("/usr/bin/pmset", ["displaysleepnow"])
            return r.ok ? "screen locked (display sleeping)" : "error: \(r.out)"
        case "sleep":
            let r = osascript("tell application \"System Events\" to sleep")
            return r.ok ? "going to sleep, sir" : "error: \(r.out)"
        case "dark_mode":
            let r = osascript("tell application \"System Events\" to tell appearance preferences to set dark mode to not dark mode")
            return r.ok ? "appearance toggled" : "error: \(r.out) (grant System Events access)"
        case "empty_trash":
            let r = osascript("tell application \"Finder\" to empty trash")
            return r.ok ? "trash emptied" : "error: \(r.out)"
        default:
            return "error: action must be lock | sleep | dark_mode | empty_trash"
        }
    }

    // MARK: - Shortcuts

    static func runShortcut(args: Args) -> String {
        guard let name = args.string("name") else { return "error: missing 'name'" }
        var a = ["run", name]
        var stdinData: Data? = nil
        if let input = args.string("input"), !input.isEmpty {
            a += ["--input-path", "-"]
            stdinData = input.data(using: .utf8)
        }
        let proc = Process()
        proc.launchPath = "/usr/bin/shortcuts"
        proc.arguments = a
        let outPipe = Pipe()
        proc.standardOutput = outPipe
        proc.standardError = outPipe
        if let d = stdinData {
            let inPipe = Pipe()
            proc.standardInput = inPipe
            do { try proc.run() } catch { return "error: \(error.localizedDescription)" }
            inPipe.fileHandleForWriting.write(d)
            inPipe.fileHandleForWriting.closeFile()
        } else {
            do { try proc.run() } catch { return "error: \(error.localizedDescription)" }
        }
        proc.waitUntilExit()
        var out = String(data: outPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        out = out.trimmingCharacters(in: .whitespacesAndNewlines)
        if proc.terminationStatus != 0 { return "error: \(out.isEmpty ? "shortcut failed" : out)" }
        return out.isEmpty ? "shortcut '\(name)' ran (no output)" : out
    }

    static func listShortcuts() -> String {
        let r = shell("/usr/bin/shortcuts", ["list"])
        if !r.ok { return "error: \(r.out)" }
        return r.out.isEmpty ? "no shortcuts installed" : r.out
    }

    // MARK: - Timer / weather / calculator

    static func timerSet(args: Args) -> String {
        guard let mStr = args.string("minutes"), let minutes = Double(mStr), minutes > 0, minutes <= 720 else {
            return "error: 'minutes' must be a number between 0 and 720"
        }
        let message = args.string("message") ?? "Time's up, sir."
        Task { @MainActor in
            try? await Task.sleep(nanoseconds: UInt64(minutes * 60 * 1_000_000_000))
            _ = osascript("display notification \"\(escAS(message))\" with title \"Hands AI Timer\" sound name \"Glass\"")
        }
        let mins = minutes == floor(minutes) ? String(Int(minutes)) : String(minutes)
        return "timer set: \(mins) min — \"\(message)\" (fires while the app is running)"
    }

    static func weather(args: Args) async -> String {
        let loc = (args.string("location") ?? "")
            .addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? ""
        guard let url = URL(string: "https://wttr.in/\(loc)?format=%l:+%C+%t+(feels+%f),+wind+%w,+humidity+%h,+precip+%p") else {
            return "error: bad location"
        }
        var req = URLRequest(url: url)
        req.setValue("curl/8", forHTTPHeaderField: "User-Agent")
        req.timeoutInterval = 15
        do {
            let (data, _) = try await URLSession.shared.data(for: req)
            let text = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            return text.isEmpty ? "error: no weather data" : text
        } catch {
            return "error: \(error.localizedDescription)"
        }
    }

    static func calculate(args: Args) -> String {
        guard let expr = args.string("expression") else { return "error: missing 'expression'" }
        // bc uses ^ natively with -l math lib; guard against shell injection by
        // feeding via stdin, not -c interpolation.
        let proc = Process()
        proc.launchPath = "/usr/bin/bc"
        proc.arguments = ["-l"]
        let inPipe = Pipe(), outPipe = Pipe()
        proc.standardInput = inPipe
        proc.standardOutput = outPipe
        proc.standardError = outPipe
        do { try proc.run() } catch { return "error: \(error.localizedDescription)" }
        inPipe.fileHandleForWriting.write(Data((expr + "\n").utf8))
        inPipe.fileHandleForWriting.closeFile()
        proc.waitUntilExit()
        let out = String(data: outPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return out.isEmpty ? "error: could not evaluate" : "\(expr) = \(out)"
    }
}
