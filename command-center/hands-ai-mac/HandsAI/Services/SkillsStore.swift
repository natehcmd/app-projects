import Foundation

/// Loadable skills: markdown playbooks in ~/hands-ai-skills/, one file per skill.
/// Format: first line `# Skill Name`, optional `> one-line description`, then the
/// body — step-by-step instructions the model follows when the skill is invoked.
/// The agent sees name+description in its system prompt and pulls the full body
/// on demand via the use_skill tool.
struct Skill: Identifiable, Equatable {
    var id: String { slug }
    let slug: String        // filename without .md
    let name: String
    let description: String
    let body: String
}

@MainActor
final class SkillsStore: ObservableObject {
    @Published var skills: [Skill] = []

    static let directory = (NSHomeDirectory() as NSString).appendingPathComponent("hands-ai-skills")

    init() {
        seedIfNeeded()
        reload()
    }

    func reload() {
        let fm = FileManager.default
        guard let entries = try? fm.contentsOfDirectory(atPath: Self.directory) else {
            skills = []; return
        }
        skills = entries
            .filter { $0.hasSuffix(".md") }
            .sorted()
            .compactMap { file in
                let path = (Self.directory as NSString).appendingPathComponent(file)
                guard let body = try? String(contentsOfFile: path, encoding: .utf8) else { return nil }
                return Self.parse(slug: String(file.dropLast(3)), body: body)
            }
    }

    static func parse(slug: String, body: String) -> Skill {
        var name = slug
        var description = ""
        for line in body.split(separator: "\n", omittingEmptySubsequences: false).prefix(6) {
            let t = line.trimmingCharacters(in: .whitespaces)
            if t.hasPrefix("# ") && name == slug { name = String(t.dropFirst(2)) }
            else if t.hasPrefix("> ") && description.isEmpty { description = String(t.dropFirst(2)) }
        }
        return Skill(slug: slug, name: name, description: description, body: body)
    }

    func skill(named query: String) -> Skill? {
        let q = query.lowercased().trimmingCharacters(in: .whitespaces)
        return skills.first { $0.slug.lowercased() == q || $0.name.lowercased() == q }
            ?? skills.first { $0.slug.lowercased().contains(q) || $0.name.lowercased().contains(q) }
    }

    /// One line per skill, injected into the system prompt.
    var promptSummary: String {
        guard !skills.isEmpty else { return "(no skills installed)" }
        return skills.map { "- \($0.slug): \($0.description.isEmpty ? $0.name : $0.description)" }
            .joined(separator: "\n")
    }

    // MARK: - Starter skills

    /// Bump when new starter skills ship; seedIfNeeded tops up missing files
    /// exactly once per version so deleted skills stay deleted afterwards.
    private static let seedVersion = 2
    private static let seedVersionKey = "skills.seedVersion"

    private func seedIfNeeded() {
        let fm = FileManager.default
        let defaults = UserDefaults.standard

        if !fm.fileExists(atPath: Self.directory) {
            try? fm.createDirectory(atPath: Self.directory, withIntermediateDirectories: true)
            for (file, content) in Self.starterSkills {
                let path = (Self.directory as NSString).appendingPathComponent(file)
                try? content.write(toFile: path, atomically: true, encoding: .utf8)
            }
            defaults.set(Self.seedVersion, forKey: Self.seedVersionKey)
            return
        }

        // Existing install: write only starter skills that aren't on disk, and
        // only once per seed version — never overwrite the user's edits.
        guard defaults.integer(forKey: Self.seedVersionKey) < Self.seedVersion else { return }
        for (file, content) in Self.starterSkills {
            let path = (Self.directory as NSString).appendingPathComponent(file)
            guard !fm.fileExists(atPath: path) else { continue }
            try? content.write(toFile: path, atomically: true, encoding: .utf8)
        }
        defaults.set(Self.seedVersion, forKey: Self.seedVersionKey)
    }

    static let starterSkills: [String: String] = [
        "daily-briefing.md": """
        # Daily Briefing
        > Morning rundown: system health, calendar, and headlines in one pass.

        When asked for a briefing, daily rundown, or "what's my day look like":
        1. Call get_stats for a one-line system health check.
        2. Run AppleScript to read today's calendar: \
        `tell application "Calendar" to get summary of every event of every calendar whose start date > (current date) - 1 * hours and start date < (current date) + 18 * hours` \
        — if Calendar access is denied, say so and move on.
        3. Call web_search for "top technology news today" and pick the 3 biggest items.
        4. Deliver it as three short spoken sentences: machine status, next events, one headline.
        """,

        "system-checkup.md": """
        # System Checkup
        > Deep health scan: disk hogs, heavy processes, battery, updates.

        When asked to check the machine over:
        1. get_stats for the baseline.
        2. run_bash `df -h / && echo --- && du -xsh ~/Library/Caches 2>/dev/null` for disk.
        3. run_bash `ps -Ao %cpu,%mem,comm -r | head -8` for heavy processes.
        4. run_bash `pmset -g batt` for battery health.
        5. Report only what's abnormal — if all is well, say one calm sentence.
        """,

        "quick-note.md": """
        # Quick Note
        > Capture a thought into Apple Notes without opening the app.

        When asked to note something down, remember something, or save a thought:
        1. Use run_applescript: \
        `tell application "Notes" to make new note at folder "Notes" with properties {name:"<short title>", body:"<the note text>"}`
        2. Confirm in one short sentence with the note title used.
        3. If Notes access is denied, fall back to appending to ~/hands-ai-notes.md via write_file (read it first, append, rewrite).
        """,

        "focus-mode.md": """
        # Focus Mode
        > Clear the decks: quiet the Mac and open the work apps.

        When asked to set up for focus, deep work, or "get me ready to work":
        1. run_applescript to quit distracting apps: \
        `tell application "Messages" to quit` (repeat for Mail, Music if running — ignore errors).
        2. open_app the user's work apps (default: "Visual Studio Code" and "Terminal"; ask once if unsure).
        3. notify with title "Focus Mode" and message "Distractions closed. Everything's ready, sir."
        4. Keep the spoken confirmation to one sentence.
        """,

        "clipboard-summary.md": """
        # Clipboard Summary
        > Summarize whatever is on the clipboard — spoken TL;DR, optional replace.

        When asked to summarize the clipboard, "what did I just copy", or to TL;DR copied text:
        1. clipboard_read to get the text. If it's empty or not text, say so and stop.
        2. Summarize it yourself: 2-3 sentences, plain language, keep names and numbers.
        3. Speak the summary. If the source text is long (over ~2000 characters), also mention roughly how long it was ("that was about three pages").
        4. Only if the user explicitly asks to replace or copy the summary: clipboard_write it back. Never overwrite the clipboard unprompted.
        """,

        "timers-and-reminders.md": """
        # Timers & Reminders
        > Pick the right tool for "remind me" — a timer for minutes, a Reminder for later.

        When asked to set a timer, remind about something, or "don't let me forget":
        1. Decide the horizon. Under ~2 hours and phrased like a countdown ("in 20 minutes") → timer_set with the duration and a short label. Anything at a clock time, tomorrow, or date-based → reminders_add.
        2. For reminders_add, put the *task* in the title, not the word "reminder", and include the due date/time.
        3. If no time was given at all, ask one short question ("For when, sir?") instead of guessing.
        4. Confirm in one sentence, echoing the time back ("Timer set — twenty minutes, tea.").
        5. If asked what's pending, use reminders_list and read out only today's and overdue items.
        """,

        "app-launcher.md": """
        # App Launcher
        > Open apps and whole workspaces by name, with fuzzy matching.

        When asked to open, launch, or switch to an app — or to "set up" a named workspace:
        1. Single app: open_app with the exact name. If it fails, list_apps and pick the closest match (e.g. "vs code" → "Visual Studio Code", "chrome" → "Google Chrome"), then open_app again.
        2. A workspace request ("set up for coding / writing / meetings") means several apps: open each with open_app, and open_url for any sites that belong to it (e.g. meetings → Calendar + open_url the video-call page if one was mentioned).
        3. Websites are not apps: "open youtube" → open_url https://youtube.com.
        4. Confirm with one short sentence listing what was opened; if something failed, name only the one that failed.
        """,

        "research-summary.md": """
        # Research Summary
        > Multi-source web research with a spoken TL;DR and a saved report.

        When asked to research a topic properly:
        1. web_search the topic; pick the 3 most credible results.
        2. web_fetch each result and extract the key facts.
        3. write_file a markdown report to ~/hands-ai-reports/<topic-slug>.md with sources listed.
        4. Speak a 2-sentence TL;DR and mention where the report was saved.
        """,
    ]
}
