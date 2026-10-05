import Foundation

public struct QueueItem: Codable, Identifiable, Equatable {
    public enum Status: String, Codable { case queued, sent, failed }
    public var id: UUID
    public var url: String
    public var note: String
    public var savedAt: Date
    public var status: Status
    public var lastError: String?

    public init(id: UUID = UUID(), url: String, note: String = "", savedAt: Date = Date(),
                status: Status = .queued, lastError: String? = nil) {
        self.id = id; self.url = url; self.note = note; self.savedAt = savedAt
        self.status = status; self.lastError = lastError
    }
}

/// Small JSON-file queue shared between the app and the share extension via the App Group.
public final class SaveQueue {
    public static let groupID = "group.com.natehoward.agentdrop"
    public let fileURL: URL

    public init(fileURL: URL) { self.fileURL = fileURL }

    public static func shared() -> SaveQueue {
        let dir = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: groupID)
            ?? FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        return SaveQueue(fileURL: dir.appendingPathComponent("queue.json"))
    }

    public func load() -> [QueueItem] {
        var result: [QueueItem] = []
        coordinate(write: false) { url in
            guard let data = try? Data(contentsOf: url) else { return }
            let dec = JSONDecoder(); dec.dateDecodingStrategy = .iso8601
            result = (try? dec.decode([QueueItem].self, from: data)) ?? []
        }
        return result
    }

    @discardableResult
    public func append(url: String, note: String = "") -> QueueItem {
        let item = QueueItem(url: url, note: note)
        mutate { $0.append(item) }
        return item
    }

    public func update(_ id: UUID, status: QueueItem.Status, error: String? = nil) {
        mutate { items in
            if let i = items.firstIndex(where: { $0.id == id }) {
                items[i].status = status
                items[i].lastError = error
            }
        }
    }

    public func delete(_ id: UUID) { mutate { $0.removeAll { $0.id == id } } }

    public func pending() -> [QueueItem] { load().filter { $0.status != .sent } }

    private func mutate(_ change: @escaping (inout [QueueItem]) -> Void) {
        coordinate(write: true) { url in
            var items: [QueueItem] = []
            let dec = JSONDecoder(); dec.dateDecodingStrategy = .iso8601
            if let data = try? Data(contentsOf: url) { items = (try? dec.decode([QueueItem].self, from: data)) ?? [] }
            change(&items)
            let enc = JSONEncoder(); enc.dateEncodingStrategy = .iso8601
            if let out = try? enc.encode(items) { try? out.write(to: url, options: .atomic) }
        }
    }

    private func coordinate(write: Bool, _ body: (URL) -> Void) {
        let coordinator = NSFileCoordinator()
        var err: NSError?
        let handler: (URL) -> Void = { body($0) }
        if write {
            coordinator.coordinate(writingItemAt: fileURL, options: .forMerging, error: &err, byAccessor: handler)
        } else {
            coordinator.coordinate(readingItemAt: fileURL, options: [], error: &err, byAccessor: handler)
        }
        if err != nil { body(fileURL) }
    }
}
