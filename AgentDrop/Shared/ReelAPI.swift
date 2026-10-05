import Foundation

/// Maps a saved URL to the id Command Center stores (the Instagram shortcode).
/// TikTok / YouTube have no id there yet, so they return nil.
public enum ReelID {
    public static func from(url: String) -> String? {
        guard let u = URL(string: url.trimmingCharacters(in: .whitespacesAndNewlines)),
              let host = u.host?.lowercased(),
              host == "instagram.com" || host == "www.instagram.com" else { return nil }
        let parts = u.path.split(separator: "/").map(String.init)
        guard parts.count >= 2, ["reel", "reels", "p"].contains(parts[0].lowercased()) else { return nil }
        let id = parts[1]
        return isValid(id) ? id : nil
    }

    /// Same rule Command Center and Hammond enforce.
    public static func isValid(_ id: String) -> Bool {
        id.range(of: "^[A-Za-z0-9_-]{5,64}$", options: .regularExpression) != nil
    }
}

public struct ReelLink: Codable, Equatable, Identifiable {
    public var url: String
    public var title: String?
    public var summary: [String]?
    public var checked: String?     // "verified" | "unsure"
    public var kind: String?
    public var id: String { url }
}

public struct ReelDetail: Codable, Equatable {
    public var id: String
    public var url: String?
    public var title: String?
    public var description: [String]?
    public var links: [ReelLink]?
    public var checked: String?
    public var status: String       // processing | ready | error | not_found
    public var topic: String?
    public var transcript: String?
}

public struct ChatMessage: Codable, Equatable, Identifiable {
    public var id: UUID
    public var role: String         // "user" | "assistant"
    public var text: String
    public var checked: String?
    public var date: Date
    public init(id: UUID = UUID(), role: String, text: String, checked: String? = nil, date: Date = Date()) {
        self.id = id; self.role = role; self.text = text; self.checked = checked; self.date = date
    }
}

/// Per-reel chat history, one JSON file per reel in the App Group container.
public final class ChatStore {
    public let directory: URL
    static let maxMessages = 200
    public init(directory: URL) { self.directory = directory }

    public static func shared() -> ChatStore {
        let base = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: SaveQueue.groupID)
            ?? FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        return ChatStore(directory: base.appendingPathComponent("chats", isDirectory: true))
    }

    private func file(_ reelID: String) -> URL? {
        ReelID.isValid(reelID) ? directory.appendingPathComponent(reelID + ".json") : nil  // never a path from outside
    }

    public func load(_ reelID: String) -> [ChatMessage] {
        guard let f = file(reelID), let data = try? Data(contentsOf: f) else { return [] }
        let dec = JSONDecoder(); dec.dateDecodingStrategy = .iso8601
        return (try? dec.decode([ChatMessage].self, from: data)) ?? []
    }

    public func append(_ reelID: String, _ msg: ChatMessage) {
        guard let f = file(reelID) else { return }
        var all = load(reelID)
        all.append(msg)
        if all.count > Self.maxMessages { all.removeFirst(all.count - Self.maxMessages) }
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let enc = JSONEncoder(); enc.dateEncodingStrategy = .iso8601
        if let out = try? enc.encode(all) { try? out.write(to: f, options: .atomic) }
    }

    public func clear(_ reelID: String) { if let f = file(reelID) { try? FileManager.default.removeItem(at: f) } }

    /// Last `n` turns in the shape the chat endpoint wants.
    public func history(_ reelID: String, last n: Int = 10) -> [[String: String]] {
        load(reelID).suffix(n).map { ["role": $0.role, "text": $0.text] }
    }
}

public enum DetailResult: Equatable {
    case detail(ReelDetail)
    case notFound
    case failed(String)
}

public enum ChatResult: Equatable {
    case answer(String, checked: String)
    case failed(String)
}

/// Phone-side calls to Hammond's /reel, /reel/chat and /reels, all through the Sender's
/// host + token handling.
extension Sender {
    static func authed(_ path: String, query: [URLQueryItem] = [], method: String = "GET",
                       body: Data? = nil, timeout: TimeInterval) -> URLRequest? {
        let address = ConnectionStore.address, token = ConnectionStore.token
        guard let base = baseURL(address), !token.isEmpty else { return nil }
        var comps = URLComponents(url: base.appendingPathComponent(path), resolvingAgainstBaseURL: false)
        if !query.isEmpty { comps?.queryItems = query }
        guard let url = comps?.url else { return nil }
        var req = URLRequest(url: url, timeoutInterval: timeout)
        req.httpMethod = method
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        if let body { req.httpBody = body; req.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        return req
    }

    public static func fetchDetail(id: String) async -> DetailResult {
        guard ReelID.isValid(id) else { return .failed("Not a valid reel id") }
        guard let req = authed("reel", query: [URLQueryItem(name: "id", value: id)], timeout: 20) else {
            return .failed("Set up your Mac in the AgentDrop app")
        }
        do {
            let (data, resp) = try await session(20).data(for: req)
            switch (resp as? HTTPURLResponse)?.statusCode ?? 0 {
            case 200:
                let d = try JSONDecoder().decode(ReelDetail.self, from: data)
                return .detail(d)
            case 404: return .notFound
            case 401: return .failed("Token rejected by your Mac")
            case let c: return .failed("Your Mac returned \(c)")
            }
        } catch is DecodingError { return .failed("Unexpected reply from your Mac") }
        catch { return .failed("Can't reach your Mac") }
    }

    public static func chat(id: String, message: String, history: [[String: String]]) async -> ChatResult {
        guard ReelID.isValid(id) else { return .failed("Not a valid reel id") }
        let payload: [String: Any] = ["id": id, "message": message, "history": history]
        guard let body = try? JSONSerialization.data(withJSONObject: payload),
              let req = authed("reel/chat", method: "POST", body: body, timeout: 150) else {
            return .failed("Set up your Mac in the AgentDrop app")
        }
        do {
            let (data, resp) = try await session(150).data(for: req)
            let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
            guard code == 200 else { return .failed(code == 401 ? "Token rejected by your Mac" : "Your Mac returned \(code)") }
            let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
            guard let a = obj?["answer"] as? String, !a.isEmpty else { return .failed("Empty answer") }
            return .answer(a, checked: obj?["checked"] as? String ?? "not checked")
        } catch { return .failed("Can't reach your Mac") }
    }
}
