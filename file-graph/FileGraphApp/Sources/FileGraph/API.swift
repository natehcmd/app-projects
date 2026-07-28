import Foundation
import SwiftUI

// Backend lives in the Python project; the app auto-starts it if needed.
enum Backend {
    static let base = URL(string: "http://127.0.0.1:8437")!
    static let projectDir = "\(NSHomeDirectory())/Projects/file-graph"

    static func ensureRunning() async {
        if await isUp() { return }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "\(projectDir)/.venv/bin/python")
        p.arguments = ["-m", "filegraph", "serve"]
        p.currentDirectoryURL = URL(fileURLWithPath: projectDir)
        p.standardOutput = FileHandle.nullDevice
        p.standardError = FileHandle.nullDevice
        try? p.run()
        for _ in 0..<20 {
            try? await Task.sleep(nanoseconds: 300_000_000)
            if await isUp() { return }
        }
    }

    static func isUp() async -> Bool {
        var req = URLRequest(url: base.appendingPathComponent("api/stats"))
        req.timeoutInterval = 1
        return (try? await URLSession.shared.data(for: req)) != nil
    }

    static func get<T: Decodable>(_ path: String, _ query: [String: String] = [:]) async throws -> T {
        var comps = URLComponents(url: base.appendingPathComponent(path), resolvingAgainstBaseURL: false)!
        if !query.isEmpty {
            comps.queryItems = query.map { URLQueryItem(name: $0.key, value: $0.value) }
        }
        let (data, _) = try await URLSession.shared.data(from: comps.url!)
        return try JSONDecoder().decode(T.self, from: data)
    }

    static func post(_ path: String, json: [String: Any] = [:]) async {
        var req = URLRequest(url: base.appendingPathComponent(path))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? JSONSerialization.data(withJSONObject: json)
        _ = try? await URLSession.shared.data(for: req)
    }

    static func delete(_ path: String) async {
        var req = URLRequest(url: base.appendingPathComponent(path))
        req.httpMethod = "DELETE"
        _ = try? await URLSession.shared.data(for: req)
    }
}

struct FileItem: Decodable, Identifiable {
    var id: String { path }
    let path: String
    let name: String
    let kind: String
    let is_dir: Int
    var is_cloud: Int? = 0
    var is_project_root: Int? = 0
    var size: Int? = 0
    var child_count: Int? = 0
    var allowed: Bool? = true
    var score: Double? = nil
    var isDir: Bool { is_dir == 1 }
}

struct TreeResponse: Decodable { let path: String; let children: [FileItem] }
struct SearchResponse: Decodable { let results: [FileItem] }
struct RelatedResponse: Decodable {
    var file: FileItem? = nil
    var siblings: [FileItem]? = []
    var semantic: [FileItem]? = []
}
struct AccessRule: Decodable, Identifiable { let id: Int; let prefix: String; let allow: Int }
struct RulesResponse: Decodable { let rules: [AccessRule] }
struct Stats: Decodable { let files: Int; let embedded: Int }

// Nate's pastel-on-dark palette — node color encodes file kind.
enum Palette {
    static let background = Color(red: 0.051, green: 0.059, blue: 0.078)
    static let kinds: [String: Color] = [
        "folder": Color(red: 0.647, green: 0.706, blue: 0.988),
        "code":   Color(red: 0.525, green: 0.937, blue: 0.675),
        "doc":    Color(red: 0.976, green: 0.659, blue: 0.831),
        "data":   Color(red: 0.988, green: 0.827, blue: 0.302),
        "image":  Color(red: 0.404, green: 0.910, blue: 0.976),
        "video":  Color(red: 0.769, green: 0.710, blue: 0.988),
        "audio":  Color(red: 0.992, green: 0.643, blue: 0.686),
        "archive":Color(red: 0.839, green: 0.827, blue: 0.820),
        "other":  Color(red: 0.545, green: 0.565, blue: 0.627),
    ]
    static let blocked = Color(red: 0.988, green: 0.647, blue: 0.647)
    static func color(for kind: String) -> Color { kinds[kind] ?? kinds["other"]! }
}
