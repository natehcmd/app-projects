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
