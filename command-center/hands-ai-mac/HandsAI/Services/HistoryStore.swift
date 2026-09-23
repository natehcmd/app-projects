import Foundation

/// Persistent conversation history: every completed exchange (what the user
/// said, what the assistant answered) survives relaunches and is browsable in
/// the History tab. Storage mirrors MemoryStore — plain JSON in
/// `~/Library/Application Support/HandsAI/history.json`.
@MainActor
final class HistoryStore: ObservableObject {
    struct Exchange: Codable, Identifiable, Equatable {
        let id: UUID
        var userText: String
        var assistantText: String
        var provider: String   // "ollama" | "claude"
        var timestamp: Date

        init(userText: String, assistantText: String, provider: String) {
            self.id = UUID()
            self.userText = userText
            self.assistantText = assistantText
            self.provider = provider
            self.timestamp = Date()
        }
    }

    @Published private(set) var exchanges: [Exchange] = []

    private static let maxExchanges = 500

    private let fileURL: URL = {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory,
                                           in: .userDomainMask)[0]
            .appendingPathComponent("HandsAI")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("history.json")
    }()

    init() {
        load()
    }

    private func load() {
        guard let data = try? Data(contentsOf: fileURL),
              let decoded = try? JSONDecoder().decode([Exchange].self, from: data) else { return }
        exchanges = decoded
    }

    private func save() {
        if let data = try? JSONEncoder().encode(exchanges) {
            try? data.write(to: fileURL)
        }
    }

    func record(user: String, assistant: String, provider: String) {
        let u = user.trimmingCharacters(in: .whitespacesAndNewlines)
        let a = assistant.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !u.isEmpty || !a.isEmpty else { return }
        exchanges.append(Exchange(userText: u, assistantText: a, provider: provider))
        if exchanges.count > Self.maxExchanges {
            exchanges.removeFirst(exchanges.count - Self.maxExchanges)
        }
        save()
    }

    func delete(_ exchange: Exchange) {
        exchanges.removeAll { $0.id == exchange.id }
        save()
    }

    func clear() {
        exchanges.removeAll()
        save()
    }

    /// Newest day first; exchanges inside a day stay chronological.
    var groupedByDay: [(day: String, items: [Exchange])] {
        let formatter = DateFormatter()
        formatter.dateStyle = .full
        formatter.timeStyle = .none
        let calendar = Calendar.current
        var groups: [(day: String, items: [Exchange])] = []
        for exchange in exchanges.sorted(by: { $0.timestamp > $1.timestamp }) {
            let day: String
            if calendar.isDateInToday(exchange.timestamp) {
                day = "Today"
            } else if calendar.isDateInYesterday(exchange.timestamp) {
                day = "Yesterday"
            } else {
                day = formatter.string(from: exchange.timestamp)
            }
            if let last = groups.indices.last, groups[last].day == day {
                groups[last].items.insert(exchange, at: 0)
            } else {
                groups.append((day: day, items: [exchange]))
            }
        }
        return groups
    }
}
