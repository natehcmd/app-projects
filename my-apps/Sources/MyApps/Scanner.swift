import Foundation
import SwiftUI

struct MadeApp: Identifiable {
    let id: String            // path
    let name: String
    let path: String
    let kind: AppKind
    let summary: String
    let modified: Date
    let area: String          // section grouping
    var appBundle: String?    // matching .app in ~/Applications, if any
    var explicitCategory: Category?   // overrides the computed category below (used for Inspo)
    var terminalCommand: String?      // Inspo CLI entries: run this in Terminal instead of revealing a path

    var category: Category {
        if let explicitCategory { return explicitCategory }
        if kind == .skill { return .skill }
        if kind == .website { return .website }
        if appBundle != nil { return .app }
        return .project
    }

    /// The real macOS icon for installed apps (what Finder/Launchpad show);
    /// nil for projects/skills/websites, which render a generated glyph tile instead.
    /// Cached — NSWorkspace.icon(forFile:) hits disk/IconServices, and this property
    /// is read from SwiftUI view bodies, which re-evaluate on every re-render.
    var realIcon: NSImage? {
        guard let bundle = appBundle else { return nil }
        if let cached = IconCache.shared[bundle] { return cached }
        let icon = NSWorkspace.shared.icon(forFile: bundle)
        IconCache.shared[bundle] = icon
        return icon
    }
}

private enum IconCache {
    static var shared: [String: NSImage] = [:]
}

enum Category: String, CaseIterable {
    case app = "Apps"
    case skill = "Skills"
    case website = "Websites"
    case project = "Projects"
    case inspo = "Inspo"

    var openVerb: String {
        switch self {
        case .app: "Launch"
        case .skill: "View Skill"
        case .website: "Open Site"
        case .project: "Run"
        case .inspo: "Open"
        }
    }

    var sidebarIcon: String {
        switch self {
        case .app: "macwindow"
        case .skill: "sparkles"
        case .website: "safari"
        case .project: "folder"
        case .inspo: "wand.and.stars"
        }
    }
}

enum AppKind: String, CaseIterable {
    case macApp = "Mac App"
    case chromeExt = "Chrome Extension"
    case python = "Python"
    case web = "Web / Node"
    case rust = "Rust"
    case website = "Website"
    case scripts = "Scripts"
    case builtApp = "Built App"
    case skill = "Claude Skill"
    case other = "Project"

    var color: Color {
        switch self {
        case .macApp:   return Theme.lav
        case .python:   return Theme.mint
        case .web:      return Theme.peach
        case .chromeExt:return Theme.sky
        case .rust:     return Theme.rose
        case .website:  return Theme.peach
        case .builtApp: return Theme.lav
        case .skill:    return Theme.mint
        case .scripts, .other: return Theme.inkDim
        }
    }

    var icon: String {
        switch self {
        case .macApp: "macwindow"
        case .python: "chevron.left.forwardslash.chevron.right"
        case .web: "globe"
        case .chromeExt: "puzzlepiece.extension"
        case .rust: "gearshape.2"
        case .website: "safari"
        case .builtApp: "app.badge.checkmark"
        case .skill: "sparkles"
        case .scripts: "terminal"
        case .other: "folder"
        }
    }
}

enum AppScanner {
    static let home = NSHomeDirectory()

    static let scanRoots: [(dir: String, area: String)] = [
        ("\(home)/Projects", "Projects"),
        ("\(home)/Projects/app-projects", "App Projects"),
        (home, "Home"),
    ]

    static let markers = [".git", "package.json", "pyproject.toml",
                          "Package.swift", "manifest.json", "Cargo.toml",
                          "requirements.txt", "Makefile",
                          "project.yml", "index.html", "run.sh"]

    static let homeExcludes: Set<String> = [
        "Applications", "Desktop", "Documents", "Downloads", "Library",
        "Movies", "Music", "Pictures", "Public", "Sites", "Projects",
        "OneDrive", "audits", "chat-logs", "prompts", "bin",
    ]

    static func scan() -> [MadeApp] {
        let fm = FileManager.default
        var apps: [String: MadeApp] = [:]

        for root in scanRoots {
            guard let names = try? fm.contentsOfDirectory(atPath: root.dir) else { continue }
            for name in names {
                if name.hasPrefix(".") || name.hasPrefix("junk") { continue }
                if name.contains("Google Drive") || name.contains("Nexus-Vault") { continue }
                if root.area == "Home", homeExcludes.contains(name) { continue }
                // container dirs are scanned by their own root entries
                if root.area == "Projects", ["AI", "Human", "app-projects"].contains(name) { continue }
                // worktrees / build dirs inside the app-projects monorepo
                if root.area == "App Projects", [".claude", "SHARED", "node_modules"].contains(name) { continue }
                let path = "\(root.dir)/\(name)"
                var isDir: ObjCBool = false
                guard fm.fileExists(atPath: path, isDirectory: &isDir), isDir.boolValue else { continue }
                guard markers.contains(where: { fm.fileExists(atPath: "\(path)/\($0)") }) else { continue }
                guard apps[path] == nil else { continue }
                apps[path] = describe(path: path, name: name, area: root.area)
            }
        }

        // Built .app bundles in ~/Applications — link to a source project when
        // the names line up, otherwise list standalone.
        if let bundles = try? fm.contentsOfDirectory(atPath: "\(home)/Applications") {
            for bundle in bundles where bundle.hasSuffix(".app") {
                let base = bundle.replacingOccurrences(of: ".app", with: "")
                let squashed = base.lowercased().filter(\.isLetter)
                if let match = apps.values.first(where: {
                    $0.name.lowercased().filter(\.isLetter) == squashed
                        || squashed.contains($0.name.lowercased().filter(\.isLetter))
                }) {
                    apps[match.path]?.appBundle = "\(home)/Applications/\(bundle)"
                } else {
                    let path = "\(home)/Applications/\(bundle)"
                    let mtime = (try? fm.attributesOfItem(atPath: path)[.modificationDate] as? Date) ?? .distantPast
                    apps[path] = MadeApp(id: path, name: base, path: path,
                                         kind: .builtApp, summary: "Standalone app bundle",
                                         modified: mtime,
                                         area: "Built Apps", appBundle: path)
                }
            }
        }
        // Claude skills — every folder with a SKILL.md
        let skillsDir = "\(home)/.claude/skills"
        for name in (try? fm.contentsOfDirectory(atPath: skillsDir)) ?? [] {
            let path = "\(skillsDir)/\(name)"
            let skillFile = "\(path)/SKILL.md"
            guard fm.fileExists(atPath: skillFile) else { continue }
            let mtime = ((try? fm.attributesOfItem(atPath: skillFile)[.modificationDate] as? Date)
                .flatMap { $0 }) ?? .distantPast
            apps[path] = MadeApp(id: path, name: name, path: path, kind: .skill,
                                 summary: skillDescription(skillFile) ?? "Claude skill",
                                 modified: mtime, area: "Skills", appBundle: nil)
        }

        // Inspo — real third-party tools/repos found while researching AgentDrop
        // reels, verified legitimate (source read, star-growth sanity-checked) and
        // installed alongside anything built locally, so they can be compared.
        
        // Registered Reels Build Tools (37 built tools)
        for item in reelsBuildItems() {
            apps[item.id] = item
        }

        for item in inspoItems() {
            apps[item.id] = item
        }

        return apps.values.sorted { $0.modified > $1.modified }
    }

    
    private static func reelsBuildItems() -> [MadeApp] {
        let now = Date()
        let candidates = [
            "\(home)/Projects/app-projects/command-center/mission-control/reels-build",
            "\(home)/Projects/mission-control/reels-build",
        ]
        guard let reelsBase = candidates.first(where: {
                  FileManager.default.fileExists(atPath: "\($0)/tools_manifest.json")
              }),
              let data = try? Data(contentsOf: URL(fileURLWithPath: "\(reelsBase)/tools_manifest.json")),
              let json = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
            return []
        }
        var items: [MadeApp] = []
        for dict in json {
            guard let id = dict["id"] as? String,
                  let name = dict["name"] as? String,
                  let script = dict["script"] as? String,
                  let desc = dict["desc"] as? String else { continue }
                        let rawUsage = dict["usage"] as? String ?? "python3 \(script) --help"
            let path = "\(reelsBase)/\(id)"
            let fullCmd = "cd \"\(path)\" && \(rawUsage)"
            
            // Look up matching Xcode .app bundle in ~/Applications
            var bundleMatch: String? = nil
            let appsDir = "\(home)/Applications"
            if let bundles = try? FileManager.default.contentsOfDirectory(atPath: appsDir) {
                let targetSquashed = name.lowercased().filter(\.isLetter)
                for b in bundles where b.hasSuffix(".app") {
                    let bSquashed = b.replacingOccurrences(of: ".app", with: "").lowercased().filter(\.isLetter)
                    if b.contains(id) || bSquashed == targetSquashed || bSquashed.contains(targetSquashed) || targetSquashed.contains(bSquashed) {
                        bundleMatch = "\(appsDir)/\(b)"
                        break
                    }
                }
            }
            
            let item = MadeApp(id: "reel:\(id)", name: name, path: path, kind: .builtApp,
                               summary: desc, modified: now, area: "Reel Apps", appBundle: bundleMatch,
                               explicitCategory: .app, terminalCommand: fullCmd)
            items.append(item)
        }
        return items
    }

    private static func inspoItems() -> [MadeApp] {
        let now = Date()
        func item(_ name: String, _ summary: String, path: String, cmd: String? = nil) -> MadeApp {
            MadeApp(id: "inspo:\(name)", name: name, path: path, kind: .other,
                    summary: summary, modified: now, area: "Inspo", appBundle: nil,
                    explicitCategory: .inspo, terminalCommand: cmd)
        }
        return [
            item("skills", "Vercel Labs' open skills CLI — discover and install Claude Skills.",
                 path: "\(home)/.npm-global/lib/node_modules/skills", cmd: "skills find"),
            item("ruflo", "ruvnet/claude-flow — multi-agent orchestration CLI.",
                 path: "\(home)/.npm-global/lib/node_modules/ruflo", cmd: "ruflo --help"),
            item("jcode", "Rust coding-agent CLI, built from source (9.5k+ stars, organic growth).",
                 path: "\(home)/Projects/jcode", cmd: "jcode --version"),
            item("markitdown", "Microsoft's file-to-Markdown converter.",
                 path: "/opt/homebrew/bin/markitdown", cmd: "markitdown --help"),
            item("claude-cookbooks", "Official Anthropic example notebooks and recipes.",
                 path: "\(home)/Learning/claude-cookbooks"),
            item("anthropic-courses", "Official Anthropic educational courses.",
                 path: "\(home)/Learning/anthropic-courses"),
            item("Camoufox", "Anti-detect Playwright-based browser automation.",
                 path: "\(home)/Projects/mission-control/reels-build/DanS4w5lcoZ",
                 cmd: "\(home)/Projects/mission-control/reels-build/DanS4w5lcoZ/.venv/bin/camoufox --help"),
            item("Hyperframes", "npm package discovered alongside Camoufox in the same reel.",
                 path: "/opt/homebrew/lib/node_modules/hyperframes"),
            item("awesome-claude-skills", "Curated, actively-maintained list of real Claude Skills (14k+ stars, organic growth) — found during the deep web-research pass on reels with no direct link.",
                 path: "\(home)/Learning/awesome-claude-skills"),
            item("ECC (everything-claude-code)", "119 skills/subagents/hooks framework, real Anthropic hackathon winner — installed project-scoped (not global) in ECC-eval to avoid touching your main Claude Code config.",
                 path: "\(home)/Projects/ECC-eval"),

            item("Kickbacks", "Statusline and editor token monetization integration.",
                 path: "\(home)/.local/bin/kickbacks", cmd: "kickbacks --status"),
            item("Vayne Lead Finder", "Open-source compliant B2B lead finder CLI tool.",
                 path: "\(home)/Projects/mission-control/reels-build/DYKSh1iv8nP", cmd: "python3 \(home)/Projects/mission-control/reels-build/DYKSh1iv8nP/lead_finder.py --help"),
            item("claude-ads", "33 ad auditing skills across Meta, Google, TikTok, YouTube, and LinkedIn.",
                 path: "\(home)/Projects/mission-control/reels-build/DanS4w5lcoZ/claude-ads", cmd: "python3 \(home)/Projects/mission-control/reels-build/DanS4w5lcoZ/claude-ads/claude_ads_core/cli.py --help"),
            item("free-claude-code", "Routes Claude Code/Codex/Pi through free/local model backends — real, verified via GitHub Trending + community reports, not fake stars.",
                 path: "\(home)/.local/bin/fcc-server", cmd: "fcc-server --version"),
        ]
    }

    /// `description:` from SKILL.md frontmatter; handles folded (`>`) values.
    private static func skillDescription(_ file: String) -> String? {
        guard let text = try? String(contentsOfFile: file, encoding: .utf8) else { return nil }
        let lines = text.split(separator: "\n", omittingEmptySubsequences: false)
        for (i, raw) in lines.enumerated() where raw.hasPrefix("description:") {
            var value = raw.dropFirst("description:".count)
                .trimmingCharacters(in: .whitespaces)
            if value == ">" || value == "|" || value.isEmpty {
                value = lines.dropFirst(i + 1)
                    .first { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
                    .map { $0.trimmingCharacters(in: .whitespaces) } ?? ""
            }
            return value.isEmpty ? nil : String(value.prefix(160))
        }
        return nil
    }

            static func open(_ app: MadeApp) {
        let fm = FileManager.default
        
        // 1. Explicit appBundle on item
        if let bundle = app.appBundle, fm.fileExists(atPath: bundle) {
            NSWorkspace.shared.open(URL(fileURLWithPath: bundle))
            return
        }
        
        // 2. Search ~/Applications for matching Xcode .app bundle
        let appsDir = "\(home)/Applications"
        if let bundles = try? fm.contentsOfDirectory(atPath: appsDir) {
            let cleanId = app.id.replacingOccurrences(of: "reel:", with: "").replacingOccurrences(of: "inspo:", with: "")
            let targetSquashed = app.name.lowercased().filter(\.isLetter)
            
            for b in bundles where b.hasSuffix(".app") {
                let bundlePath = "\(appsDir)/\(b)"
                let bSquashed = b.replacingOccurrences(of: ".app", with: "").lowercased().filter(\.isLetter)
                
                if b.contains(cleanId) || bSquashed == targetSquashed || (targetSquashed.count > 3 && bSquashed.contains(targetSquashed)) {
                    NSWorkspace.shared.open(URL(fileURLWithPath: bundlePath))
                    return
                }
            }
        }

        // 3. Explicit terminal command (Reels / Inspo entries)
        if let cmd = app.terminalCommand {
            runInTerminal(cmd, workingDir: app.path)
            return
        }

        // 4. Actually run the project — detect how, don't just reveal a folder.
        if fm.fileExists(atPath: app.path), launchProject(app.path) { return }

        // 5. Last resort: reveal in Finder
        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: app.path)])
    }

    /// Figures out how a project starts and starts it. Returns false if it
    /// can't tell (caller then reveals the folder in Finder).
    static func launchProject(_ path: String) -> Bool {
        let fm = FileManager.default
        let has = { (f: String) in fm.fileExists(atPath: "\(path)/\(f)") }
        let entries = (try? fm.contentsOfDirectory(atPath: path)) ?? []
        let first = { (suffix: String) in entries.first { $0.hasSuffix(suffix) } }

        // run scripts win — the author already said how to start it
        for script in ["run.sh", "start.sh", "start.command", "dev.sh"] where has(script) {
            runInTerminal("bash \"\(path)/\(script)\"", workingDir: path); return true
        }
        // Xcode / SwiftPM app
        if let proj = first(".xcworkspace") ?? first(".xcodeproj") {
            NSWorkspace.shared.open(URL(fileURLWithPath: "\(path)/\(proj)")); return true
        }
        if has("project.yml") {   // xcodegen — generate then open
            runInTerminal("command -v xcodegen >/dev/null && xcodegen generate; open *.xcodeproj", workingDir: path)
            return true
        }
        if has("Package.swift") {
            let swiftUI = (try? String(contentsOfFile: "\(path)/Package.swift", encoding: .utf8))?.contains(".executable") ?? false
            runInTerminal(swiftUI ? "swift run" : "open Package.swift", workingDir: path); return true
        }
        // Node — prefer an explicit script
        if has("package.json"),
           let pkg = try? String(contentsOfFile: "\(path)/package.json", encoding: .utf8) {
            let script = ["dev", "start", "serve"].first { pkg.contains("\"\($0)\"") }
            runInTerminal("npm install --silent; npm run \(script ?? "start")", workingDir: path); return true
        }
        // Rust
        if has("Cargo.toml") { runInTerminal("cargo run", workingDir: path); return true }
        // Python service
        for py in ["server.py", "app.py", "main.py"] where has(py) {
            runInTerminal("[ -d .venv ] && source .venv/bin/activate; python3 \(py)", workingDir: path); return true
        }
        if has("pyproject.toml") || has("requirements.txt") {
            runInTerminal("python3 -m venv .venv 2>/dev/null; source .venv/bin/activate; pip install -q -e . 2>/dev/null || pip install -q -r requirements.txt; python3 -m \((path as NSString).lastPathComponent.replacingOccurrences(of: "-", with: "_")) 2>/dev/null || $SHELL", workingDir: path)
            return true
        }
        // Chrome extension
        if has("manifest.json") {
            NSWorkspace.shared.open(URL(string: "chrome://extensions")!)
            NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)])
            return true
        }
        // Static site
        if let html = has("index.html") ? "index.html" : first(".html") {
            NSWorkspace.shared.open(URL(fileURLWithPath: "\(path)/\(html)")); return true
        }
        return false
    }

    static func runInTerminal(_ command: String, workingDir: String? = nil) {
        var execCmd = command
        if let workingDir = workingDir, !command.contains("cd ") {
            execCmd = "cd \"\(workingDir)\" && \(command)"
        }
        let cleanCmd = execCmd.replacingOccurrences(of: "\"", with: "\\\"")
        let script = "tell application \"Terminal\" to activate\ntell application \"Terminal\" to do script \"\(cleanCmd)\""
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
        p.arguments = ["-e", script]
        try? p.run()
    }

    static func openWith(_ appName: String, _ path: String) {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/open")
        p.arguments = ["-a", appName, path]
        try? p.run()
    }

    private static func describe(path: String, name: String, area: String) -> MadeApp {
        let fm = FileManager.default
        let kind: AppKind
        if fm.fileExists(atPath: "\(path)/Package.swift") { kind = .macApp }
        else if fm.fileExists(atPath: "\(path)/manifest.json") { kind = .chromeExt }
        else if fm.fileExists(atPath: "\(path)/Cargo.toml") { kind = .rust }
        else if fm.fileExists(atPath: "\(path)/pyproject.toml")
             || fm.fileExists(atPath: "\(path)/requirements.txt")
             || !((try? fm.contentsOfDirectory(atPath: path))? .filter { $0.hasSuffix(".py") }.isEmpty ?? true) { kind = .python }
        else if fm.fileExists(atPath: "\(path)/package.json") { kind = .web }
        else if fm.fileExists(atPath: "\(path)/index.html") { kind = .website }
        else if name == "scripts" { kind = .scripts }
        else { kind = .other }

        return MadeApp(id: path, name: name, path: path, kind: kind,
                       summary: readmeSummary(path) ?? defaultSummary(path),
                       modified: newestChange(path), area: area, appBundle: nil)
    }

    private static func readmeSummary(_ path: String) -> String? {
        for candidate in ["README.md", "readme.md", "README.txt", "CLAUDE.md"] {
            guard let text = try? String(contentsOfFile: "\(path)/\(candidate)",
                                         encoding: .utf8) else { continue }
            for raw in text.split(separator: "\n") {
                let line = raw.trimmingCharacters(in: .whitespaces)
                if line.isEmpty || line.hasPrefix("#") || line.hasPrefix("!")
                    || line.hasPrefix("[") || line.hasPrefix("---")
                    || line.hasPrefix("<") || line.hasPrefix("|")
                    || line.hasPrefix("```") || line.hasPrefix("*") { continue }
                return String(line.prefix(160))
            }
        }
        return nil
    }

    private static func defaultSummary(_ path: String) -> String {
        let fm = FileManager.default
        let count = (try? fm.contentsOfDirectory(atPath: path))?.count ?? 0
        return "\(count) items"
    }

    /// Newest mtime among top-level entries (dir mtime alone misses edits in subfolders).
    private static func newestChange(_ path: String) -> Date {
        let fm = FileManager.default
        var newest = (try? fm.attributesOfItem(atPath: path)[.modificationDate] as? Date)
            .flatMap { $0 } ?? .distantPast
        for entry in (try? fm.contentsOfDirectory(atPath: path)) ?? [] {
            if entry == "node_modules" || entry.hasPrefix(".") { continue }
            if let d = (try? fm.attributesOfItem(atPath: "\(path)/\(entry)")[.modificationDate] as? Date)
                .flatMap({ $0 }), d > newest { newest = d }
        }
        return newest
    }
}
