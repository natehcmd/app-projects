import Foundation

public enum SendResult: Equatable {
    case sent
    case unreachable(String)   // network problem: keep queued, retry later
    case rejected(String)      // server said no: mark failed
}

public enum Sender {
    /// "192.168.1.5:8787" or "http://host:8787" -> base URL.
    public static func baseURL(_ address: String) -> URL? {
        var a = address.trimmingCharacters(in: .whitespacesAndNewlines)
        while a.hasSuffix("/") { a.removeLast() }
        if a.isEmpty { return nil }
        if !a.lowercased().hasPrefix("http://") && !a.lowercased().hasPrefix("https://") { a = "http://" + a }
        return URL(string: a)
    }

    static func session(_ timeout: TimeInterval) -> URLSession {
        let c = URLSessionConfiguration.ephemeral
        c.timeoutIntervalForRequest = timeout
        c.timeoutIntervalForResource = timeout
        c.waitsForConnectivity = false
        return URLSession(configuration: c)
    }

    public static func send(url: String, note: String = "", address: String, token: String,
                            timeout: TimeInterval = 8) async -> SendResult {
        guard let base = baseURL(address), !token.isEmpty else { return .unreachable("Set up your Mac in the AgentDrop app") }
        var req = URLRequest(url: base.appendingPathComponent("save"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        var body: [String: String] = ["url": url]
        if !note.isEmpty { body["note"] = note }
        req.httpBody = try? JSONSerialization.data(withJSONObject: body)
        do {
            let (_, resp) = try await session(timeout).data(for: req)
            let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
            switch code {
            case 200: return .sent
            case 401: return .rejected("Token rejected by your Mac")
            case 400: return .rejected("Link not accepted")
            case 502, 503, 504: return .unreachable("Mac is up but Command Center isn't (\(code))")
            default: return .rejected("Mac returned \(code)")
            }
        } catch {
            return .unreachable("Can't reach your Mac")
        }
    }

    /// Ping, then an authenticated probe: POST /save with a bad host. 400 = token fine, 401 = wrong token.
    public static func testConnection(address: String, token: String) async -> (ok: Bool, message: String) {
        guard let base = baseURL(address) else { return (false, "Enter your Mac's address first") }
        do {
            var ping = URLRequest(url: base.appendingPathComponent("ping"))
            ping.timeoutInterval = 6
            let (data, resp) = try await session(6).data(for: ping)
            guard (resp as? HTTPURLResponse)?.statusCode == 200,
                  String(data: data, encoding: .utf8)?.contains("Hammond") == true else {
                return (false, "Something answered, but it isn't Hammond")
            }
        } catch {
            return (false, "Can't reach \(address). Same Wi-Fi as the Mac? Local Network allowed for AgentDrop in Settings?")
        }
        guard !token.isEmpty else { return (false, "Reached Hammond. Now enter the token.") }
        var probe = URLRequest(url: base.appendingPathComponent("save"))
        probe.httpMethod = "POST"
        probe.timeoutInterval = 6
        probe.setValue("application/json", forHTTPHeaderField: "Content-Type")
        probe.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        probe.httpBody = Data(#"{"url":"https://example.invalid/probe"}"#.utf8)
        do {
            let (_, resp) = try await session(6).data(for: probe)
            switch (resp as? HTTPURLResponse)?.statusCode ?? 0 {
            case 400: return (true, "Connected. Token works.")
            case 401: return (false, "Reached Hammond, but the token is wrong.")
            case let c: return (false, "Unexpected reply (\(c)).")
            }
        } catch { return (false, "Lost connection during the token check.") }
    }

    /// Try every queued/failed item. Returns number sent.
    @discardableResult
    public static func retryAll(queue: SaveQueue) async -> Int {
        let address = ConnectionStore.address, token = ConnectionStore.token
        var sent = 0
        for item in queue.pending().sorted(by: { $0.savedAt < $1.savedAt }) {
            switch await send(url: item.url, note: item.note, address: address, token: token) {
            case .sent: queue.update(item.id, status: .sent); sent += 1
            case .unreachable(let m): queue.update(item.id, status: .queued, error: m); return sent
            case .rejected(let m): queue.update(item.id, status: .failed, error: m)
            }
        }
        return sent
    }
}
