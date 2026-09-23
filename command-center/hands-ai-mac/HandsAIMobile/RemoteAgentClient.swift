import Foundation
import SwiftUI

/// iOS-side counterpart to the Mac's `AgentStore` (see Services/RemoteServer.swift,
/// Mac-only). Doesn't run any agent loop itself — it just opens a WebSocket to
/// the Mac, sends `RemoteRequest`s, and applies incoming `RemoteEvent`s to the
/// same four properties `AgentStore` publishes, so the shared `OrbView`/
/// `ToolFeedView` bind to this exactly like they bind to `AgentStore` on the Mac.
@MainActor
final class RemoteAgentClient: ObservableObject {
    enum ConnectionStatus: Equatable {
        case disconnected
        case connecting
        case connected
        case failed(String)
    }

    @Published var state: AgentState = .idle
    @Published var toolCalls: [ToolCall] = []
    @Published var transcript: [Message] = []
    @Published var liveReply: String = ""
    @Published private(set) var connectionStatus: ConnectionStatus = .disconnected

    @AppStorage("remote.host") var host: String = ""
    @AppStorage("remote.port") var port: Int = 8787
    @AppStorage("remote.token") var token: String = ""

    private var task: URLSessionWebSocketTask?
    private let session = URLSession(configuration: .ephemeral)

    var isConfigured: Bool { !host.isEmpty && !token.isEmpty }

    func connect() {
        guard isConfigured else {
            connectionStatus = .failed("Enter a host and token first.")
            return
        }
        disconnect()
        guard let url = URL(string: "ws://\(host):\(port)/agent") else {
            connectionStatus = .failed("Invalid host/port.")
            return
        }
        connectionStatus = .connecting
        let t = session.webSocketTask(with: url)
        task = t
        t.resume()
        receiveLoop()
        // Empty first message doubles as the auth handshake — the Mac
        // validates the token on the first frame regardless of content.
        sendRaw(text: "")
    }

    func disconnect() {
        task?.cancel(with: .goingAway, reason: nil)
        task = nil
        if connectionStatus != .disconnected { connectionStatus = .disconnected }
    }

    func send(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        guard task != nil else {
            connectionStatus = .failed("Not connected.")
            return
        }
        transcript.append(Message(role: .user, text: trimmed))
        sendRaw(text: trimmed)
    }

    private func sendRaw(text: String) {
        guard let task else { return }
        let req = RemoteRequest(text: text, token: token)
        guard let data = try? JSONEncoder().encode(req),
              let json = String(data: data, encoding: .utf8) else { return }
        task.send(.string(json)) { [weak self] error in
            guard let error else { return }
            Task { @MainActor in self?.connectionStatus = .failed(error.localizedDescription) }
        }
    }

    private func receiveLoop() {
        task?.receive { [weak self] result in
            guard let self else { return }
            Task { @MainActor in
                switch result {
                case .failure(let error):
                    self.connectionStatus = .failed(error.localizedDescription)
                case .success(let message):
                    if self.connectionStatus != .connected { self.connectionStatus = .connected }
                    switch message {
                    case .string(let text):
                        self.handle(text)
                    case .data(let data):
                        if let text = String(data: data, encoding: .utf8) { self.handle(text) }
                    @unknown default:
                        break
                    }
                    self.receiveLoop()
                }
            }
        }
    }

    private func handle(_ json: String) {
        guard let data = json.data(using: .utf8),
              let event = try? JSONDecoder().decode(RemoteEvent.self, from: data) else { return }
        switch event.type {
        case .delta:
            liveReply = event.text ?? ""
        case .toolCalls:
            toolCalls = event.toolCalls ?? []
        case .final:
            liveReply = ""
            if let text = event.text {
                transcript.append(Message(role: .assistant, text: text))
            }
        case .state:
            if let s = event.state { state = s }
        case .error:
            connectionStatus = .failed(event.text ?? "Server error")
        }
    }
}
