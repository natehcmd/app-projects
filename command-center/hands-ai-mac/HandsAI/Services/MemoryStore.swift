import Foundation

/// Persistent two-tier memory: things the assistant knows about the user and
/// their work, plus standing policies ("look it up yourself before asking").
/// Injected into every system prompt so the assistant never re-asks; edited
/// by the model through the remember / recall / forget tools.
@MainActor
final class MemoryStore: ObservableObject {
    struct Entry: Codable, Identifiable, Equatable {
        let id: UUID
        var tier: String       // "user" | "work" | "policy"
        var text: String
        var created: Date

        init(tier: String, text: String) {
            self.id = UUID()
            self.tier = tier
            self.text = text
            self.created = Date()
        }
    }

    @Published private(set) var entries: [Entry] = []

    static let validTiers = ["user", "work", "policy"]
    private static let maxEntries = 200

    private let fileURL: URL = {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory,
                                           in: .userDomainMask)[0]
            .appendingPathComponent("HandsAI")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("memory.json")
    }()

    init() {
        load()
    }

    private func load() {
        guard let data = try? Data(contentsOf: fileURL),
              let decoded = try? JSONDecoder().decode([Entry].self, from: data) else { return }
        entries = decoded
    }

    private func save() {
        if let data = try? JSONEncoder().encode(entries) {
            try? data.write(to: fileURL)
        }
    }

    /// Rendered into the system prompt. Compact: one line per memory.
    var promptSummary: String {
        guard !entries.isEmpty else { return "(nothing remembered yet)" }
        func section(_ tier: String, _ title: String) -> String {
            let items = entries.filter { $0.tier == tier }
            guard !items.isEmpty else { return "" }
            return "\(title):\n" + items.map { "- \($0.text)" }.joined(separator: "\n") + "\n"
        }
        return section("user", "About the user")
            + section("work", "About their work & projects")
            + section("policy", "Standing rules (always follow)")
    }

    func remember(tier: String, text: String) -> String {
        let t = Self.validTiers.contains(tier) ? tier : "user"
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return "error: empty memory text" }
        // Replace a near-duplicate instead of stacking variants.
        if let idx = entries.firstIndex(where: {
            $0.tier == t && $0.text.lowercased() == trimmed.lowercased()
        }) {
            entries[idx].text = trimmed
        } else {
            entries.append(Entry(tier: t, text: trimmed))
            if entries.count > Self.maxEntries { entries.removeFirst() }
        }
        save()
        return "remembered (\(t)): \(trimmed)"
    }

    func recall(query: String) -> String {
        let q = query.lowercased()
        let hits = q.isEmpty ? entries : entries.filter { $0.text.lowercased().contains(q) }
        guard !hits.isEmpty else { return "no memories match \"\(query)\"" }
        return hits.map { "[\($0.tier)] \($0.text)" }.joined(separator: "\n")
    }

    func forget(query: String) -> String {
        let q = query.lowercased()
        guard !q.isEmpty else { return "error: say what to forget" }
        let before = entries.count
        let removed = entries.filter { $0.text.lowercased().contains(q) }
        entries.removeAll { $0.text.lowercased().contains(q) }
        save()
        guard entries.count < before else { return "no memories match \"\(query)\"" }
        return "forgot \(removed.count): " + removed.map(\.text).joined(separator: " · ")
    }
}
