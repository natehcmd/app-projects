import Foundation
import SwiftUI
import Combine
import FlyingFox

/// Lets the iPhone remote-control app drive this Mac's real `AgentStore`
/// over a WebSocket. Doesn't duplicate any agent logic — it just calls
/// `agent.send(text)` (the same call `ChatInput`/`InputField` already make)
/// and forwards the store's existing `@Published` properties to the socket
/// as they change. Always runs on localhost so Command Center connects with
/// no setup; `enabled` (Settings → Remote) only widens it to other devices
/// (the iPhone over Tailscale). Token-authenticated either way.
@MainActor
final class RemoteServer: ObservableObject {
    @Published private(set) var isRunning = false
    @Published private(set) var lastError: String?

    /// Allow other devices (iPhone). Off = loopback only.
    @AppStorage("remote.serverEnabled") var enabled: Bool = false {
        didSet { if oldValue != enabled { restart() } }
    }
    @AppStorage("remote.port") var port: Int = 8787
    @AppStorage("remote.token") var token: String = "" {
        didSet {
            if token.isEmpty { token = Self.generateToken() }
        }
    }

    private weak var agent: AgentStore?
    private var server: HTTPServer?
    private var serverTask: Task<Void, Never>?

    static func generateToken() -> String {
        UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased()
    }

    func attach(agent: AgentStore) {
        self.agent = agent
        if token.isEmpty { token = Self.generateToken() }
        syncRunState()
    }

    private func syncRunState() {
        start()
    }

    /// Rebind after the device-access toggle changes: stop, wait for the old
    /// listener to release the port, start on the new address.
    private func restart() {
        let old = serverTask
        stop()
        Task {
            _ = await old?.value
            self.start()
        }
    }

    private func start() {
        guard serverTask == nil, let agent else { return }
        // Captured once at start rather than read live: `token` is
        // main-actor-isolated state, and the handler's `makeMessages` runs
        // off a Sendable closure per FlyingFox connection — simplest correct
        // fix is a plain snapshot. Regenerating the token while the server is
        // running requires toggling it off/on to pick up the new value
        // (documented in Settings → Remote).
        let handler = AgentWSHandler(agent: agent, expectedToken: token)
        let p = UInt16(clamping: port)
        // Loopback unless the user opted in to other devices: this agent can
        // run shell commands, so the LAN is never exposed by default.
        let server = enabled ? HTTPServer(port: p)
                             : HTTPServer(address: sockaddr_in6.loopback(port: p))
        self.server = server
        lastError = nil
        serverTask = Task {
            do {
                await server.appendRoute("GET /agent", to: .webSocket(handler))
                let saver = SaveEndpoint(expectedToken: handler.expectedToken)
                await server.appendRoute("GET /ping") { _ in saver.ping() }
                await server.appendRoute("POST /save") { req in await saver.handle(req) }
                // Phone detail screen: authenticated proxies to Command Center, nothing else.
                await server.appendRoute("GET /reel") { req in await saver.reelDetail(req) }
                await server.appendRoute("POST /reel/chat") { req in await saver.reelChat(req) }
                await server.appendRoute("GET /reels") { req in await saver.reelList(req) }
                self.isRunning = true
                try await server.run()
            } catch {
                // Cancellation (a deliberate restart) can surface as a thrown
                // error depending on where in `run()` it lands — not a failure.
                if !Task.isCancelled {
                    self.lastError = error.localizedDescription
                }
            }
            self.isRunning = false
            self.server = nil
            self.serverTask = nil
        }
    }

    private func stop() {
        // Cancelling the task is sufficient — FlyingFox terminates all
        // connections immediately when its running Task is cancelled.
        serverTask?.cancel()
    }
}

/// Bridges one WebSocket connection to the shared `AgentStore`. The first
/// frame on a connection must carry the correct token — nothing before that
/// is acted on. Multiple concurrent phone connections are each independently
/// authenticated and each get their own forwarded event stream.
private struct AgentWSHandler: WSMessageHandler {
    let agent: AgentStore
    let expectedToken: String

    func makeMessages(for client: AsyncStream<WSMessage>) async throws -> AsyncStream<WSMessage> {
        let agent = agent
        let expectedToken = expectedToken
        return AsyncStream { continuation in
            let task = Task { @MainActor in
                var authed = false
                var cancellables = Set<AnyCancellable>()

                func emit(_ event: RemoteEvent) {
                    guard let data = try? JSONEncoder().encode(event),
                          let json = String(data: data, encoding: .utf8) else { return }
                    continuation.yield(.text(json))
                }

                agent.$liveReply.dropFirst().sink { text in
                    guard authed, !text.isEmpty else { return }
                    emit(RemoteEvent(type: .delta, text: text))
                }.store(in: &cancellables)

                agent.$toolCalls.dropFirst().sink { calls in
                    guard authed else { return }
                    emit(RemoteEvent(type: .toolCalls, toolCalls: calls))
                }.store(in: &cancellables)

                agent.$state.dropFirst().sink { state in
                    guard authed else { return }
                    emit(RemoteEvent(type: .state, state: state))
                }.store(in: &cancellables)

                agent.$transcript.dropFirst().sink { transcript in
                    guard authed, let last = transcript.last else { return }
                    if last.role == .assistant {
                        emit(RemoteEvent(type: .final, text: last.text))
                    } else if last.role == .user {
                        emit(RemoteEvent(type: .user, text: last.text))
                    }
                }.store(in: &cancellables)

                agent.$pendingDenials.dropFirst().sink { denials in
                    guard authed else { return }
                    emit(RemoteEvent(type: .permission, denials: denials))
                }.store(in: &cancellables)

                for await message in client {
                    guard case .text(let json) = message,
                          let data = json.data(using: .utf8),
                          let req = try? JSONDecoder().decode(RemoteRequest.self, from: data)
                    else { continue }

                    guard !expectedToken.isEmpty, req.token == expectedToken else {
                        emit(RemoteEvent(type: .error, text: "Invalid token."))
                        continue
                    }
                    let wasAuthed = authed
                    authed = true
                    // A client only ever sees an event when AgentStore's own
                    // @Published properties change — the auth-only frame
                    // (empty text, just carrying the token) triggers no such
                    // change, so without this a client has no way to tell
                    // "invalid token" apart from "connecting forever" until
                    // a real message happens to get sent. One real state
                    // snapshot right after auth succeeds fixes that.
                    if !wasAuthed {
                        emit(RemoteEvent(type: .state, state: agent.state))
                        let history = agent.transcript.map { ChatHistoryItem(role: $0.role == .user ? "user" : "assistant", text: $0.text) }
                        if !history.isEmpty {
                            emit(RemoteEvent(type: .history, history: history))
                        }
                        if !agent.pendingDenials.isEmpty {
                            emit(RemoteEvent(type: .permission, denials: agent.pendingDenials))
                        }
                    }
                    if req.type == "permission" {
                        guard let id = req.id, let decisionRaw = req.decision,
                              let decision = ClaudeCLIClient.PermissionDecision(rawValue: decisionRaw) else {
                            emit(RemoteEvent(type: .error, text: "Malformed permission decision."))
                            continue
                        }
                        agent.decidePermission(id: id, decision: decision)
                        continue
                    }
                    if let tool = req.tool {
                        // Read-only tools only: a remote client can look, never act.
                        let remoteReadOnly: Set<String> = ["calendar_today", "reminders_list"]
                        guard remoteReadOnly.contains(tool) else {
                            emit(RemoteEvent(type: .error, text: "Tool not available remotely: \(tool)"))
                            continue
                        }
                        let out = await Tools.runMac(name: tool, args: Tools.Args([:])) ?? "error: unknown tool"
                        emit(RemoteEvent(type: .toolResult, text: out, tool: tool))
                        continue
                    }
                    let text = req.text.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !text.isEmpty {
                        agent.send(text, engineOverride: req.engine, modelOverride: req.model)
                    }
                }
                cancellables.removeAll()
                continuation.finish()
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }
}

/// `POST /save` — the AgentDrop iPhone share extension's way in. Validates a
/// reel/video URL and hands it to Command Center's ingest (download +
/// transcribe + tag). Bearer-token authenticated with the same remote token as
/// the WebSocket; an empty configured token rejects everything. `GET /ping`
/// is unauthenticated and reveals nothing but the app name.
private struct SaveEndpoint: Sendable {
    let expectedToken: String

    static let allowedHosts: Set<String> = [
        "instagram.com", "www.instagram.com",
        "tiktok.com", "www.tiktok.com", "vm.tiktok.com",
        "youtube.com", "youtu.be",
    ]
    static let maxBody = 8 * 1024
    static let ingest = URL(string: "http://127.0.0.1:8450/api/reels/add")!

    private func json(_ status: HTTPStatusCode, _ obj: [String: Any]) -> HTTPResponse {
        let data = (try? JSONSerialization.data(withJSONObject: obj)) ?? Data("{}".utf8)
        return HTTPResponse(statusCode: status, headers: [.contentType: "application/json"], body: data)
    }

    func ping() -> HTTPResponse { json(.ok, ["ok": true, "app": "Hammond"]) }

    /// Constant-time compare; empty expected token never matches.
    static func tokensMatch(_ given: String, _ expected: String) -> Bool {
        guard !expected.isEmpty else { return false }
        let a = Array(given.utf8), b = Array(expected.utf8)
        var diff = a.count ^ b.count
        for i in 0..<b.count { diff |= Int((i < a.count ? a[i] : 0) ^ b[i]) }
        return diff == 0
    }

    static func validate(_ raw: String) -> URL? {
        guard let u = URL(string: raw.trimmingCharacters(in: .whitespacesAndNewlines)),
              u.scheme?.lowercased() == "https",
              let host = u.host?.lowercased(), allowedHosts.contains(host) else { return nil }
        return u
    }

    static let ccBase = "http://127.0.0.1:8450"
    static let idPattern = try! NSRegularExpression(pattern: "^[A-Za-z0-9_-]{5,64}$")

    private func authorized(_ req: HTTPRequest) -> Bool {
        let auth = req.headers[.authorization] ?? ""
        let bearer = auth.lowercased().hasPrefix("bearer ") ? String(auth.dropFirst(7)).trimmingCharacters(in: .whitespaces) : ""
        return Self.tokensMatch(bearer, expectedToken)
    }

    static func validID(_ s: String) -> Bool {
        idPattern.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) != nil
    }

    /// Forward to Command Center with the remote token; pass its status + JSON body back.
    private func forward(_ path: String, method: String, body: Data?, timeout: TimeInterval) async -> HTTPResponse {
        guard let url = URL(string: Self.ccBase + path) else { return json(.badRequest, ["ok": false]) }
        var fwd = URLRequest(url: url, timeoutInterval: timeout)
        fwd.httpMethod = method
        fwd.setValue("Bearer \(expectedToken)", forHTTPHeaderField: "Authorization")
        if let body { fwd.httpBody = body; fwd.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        do {
            let (data, resp) = try await URLSession.shared.data(for: fwd)
            let code = (resp as? HTTPURLResponse)?.statusCode ?? 502
            // Only relay statuses the phone should understand; anything else is a gateway error.
            let status: HTTPStatusCode = code == 200 ? .ok : code == 404 ? .notFound : code == 400 ? .badRequest : .badGateway
            return HTTPResponse(statusCode: status, headers: [.contentType: "application/json"], body: data)
        } catch {
            return json(.badGateway, ["ok": false, "error": "Command Center unreachable"])
        }
    }

    func reelDetail(_ req: HTTPRequest) async -> HTTPResponse {
        guard authorized(req) else { return json(.unauthorized, ["ok": false, "error": "unauthorized"]) }
        guard let id = req.query.first(where: { $0.name == "id" })?.value, Self.validID(id) else {
            return json(.badRequest, ["ok": false, "error": "bad id"])
        }
        return await forward("/api/reels/detail?id=\(id)", method: "GET", body: nil, timeout: 20)
    }

    func reelList(_ req: HTTPRequest) async -> HTTPResponse {
        guard authorized(req) else { return json(.unauthorized, ["ok": false, "error": "unauthorized"]) }
        let n = req.query.first(where: { $0.name == "limit" }).flatMap { Int($0.value) } ?? 50
        return await forward("/api/reels/recent?limit=\(max(1, min(n, 200)))", method: "GET", body: nil, timeout: 20)
    }

    func reelChat(_ req: HTTPRequest) async -> HTTPResponse {
        guard authorized(req) else { return json(.unauthorized, ["ok": false, "error": "unauthorized"]) }
        if let len = req.headers[.contentLength].flatMap({ Int($0) }), len > 32 * 1024 {
            return json(.payloadTooLarge, ["ok": false, "error": "body too large"])
        }
        guard let body = try? await req.bodyData, body.count <= 32 * 1024,
              let obj = try? JSONSerialization.jsonObject(with: body) as? [String: Any],
              let id = obj["id"] as? String, Self.validID(id),
              let msg = obj["message"] as? String, !msg.isEmpty else {
            return json(.badRequest, ["ok": false, "error": "need id and message"])
        }
        // Rebuild the payload so only the expected fields reach Command Center.
        let clean: [String: Any] = ["id": id, "message": msg, "history": obj["history"] as? [[String: Any]] ?? []]
        guard let data = try? JSONSerialization.data(withJSONObject: clean) else { return json(.badRequest, ["ok": false]) }
        return await forward("/api/reels/chat", method: "POST", body: data, timeout: 180)
    }

    func handle(_ req: HTTPRequest) async -> HTTPResponse {
        let auth = req.headers[.authorization] ?? ""
        let bearer = auth.lowercased().hasPrefix("bearer ") ? String(auth.dropFirst(7)).trimmingCharacters(in: .whitespaces) : ""
        guard Self.tokensMatch(bearer, expectedToken) else {
            return json(.unauthorized, ["ok": false, "error": "unauthorized"])
        }
        if let len = req.headers[.contentLength].flatMap({ Int($0) }), len > Self.maxBody {
            return json(.payloadTooLarge, ["ok": false, "error": "body too large"])
        }
        guard let body = try? await req.bodyData, body.count <= Self.maxBody else {
            return json(.payloadTooLarge, ["ok": false, "error": "body too large"])
        }
        guard let obj = try? JSONSerialization.jsonObject(with: body) as? [String: Any],
              let raw = obj["url"] as? String, let url = Self.validate(raw) else {
            return json(.badRequest, ["ok": false, "error": "need an https Instagram, TikTok or YouTube url"])
        }
        var fwd = URLRequest(url: Self.ingest, timeoutInterval: 15)
        fwd.httpMethod = "POST"
        fwd.setValue("application/json", forHTTPHeaderField: "Content-Type")
        fwd.setValue("Bearer \(expectedToken)", forHTTPHeaderField: "Authorization")
        fwd.httpBody = try? JSONSerialization.data(withJSONObject: ["urls": [url.absoluteString]])
        do {
            let (data, resp) = try await URLSession.shared.data(for: fwd)
            let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
            guard code == 200 else {
                return json(.badGateway, ["ok": false, "error": "Command Center returned \(code)"])
            }
            let queued = ((try? JSONSerialization.jsonObject(with: data)) as? [String: Any])?["queued"] as? Int ?? 1
            return json(.ok, ["ok": true, "queued": queued])
        } catch {
            return json(.badGateway, ["ok": false, "error": "Command Center unreachable"])
        }
    }
}
