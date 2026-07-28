import Foundation
import SwiftUI

/// Direct client for the local Ollama server (default http://127.0.0.1:11434).
/// Supports streaming chat and native tool calling for models that expose it
/// (qwen2.5-coder, llama3.1+, devstral, hermes, etc.).
@MainActor
final class OllamaClient: ObservableObject {
    @Published var baseURL: URL = URL(string: "http://127.0.0.1:11434")!
    @Published var isReachable: Bool = false
    @Published var availableModels: [Model] = []
    @AppStorage("ollama.model") var selectedModel: String = "devstral:latest"
    @Published var lastError: String? = nil

    struct Model: Decodable, Identifiable, Hashable {
        var id: String { name }
        let name: String
        let size: Int64
        let details: Details?
        struct Details: Decodable, Hashable {
            let parameter_size: String?
            let family: String?
        }
        var sizeGB: Double { Double(size) / 1_073_741_824.0 }
    }

    private let session: URLSession = {
        let cfg = URLSessionConfiguration.ephemeral
        cfg.timeoutIntervalForRequest = 300 // long-running generation
        cfg.waitsForConnectivity = false
        return URLSession(configuration: cfg)
    }()

    init() {
        Task { await self.pingLoop() }
    }

    private func pingLoop() async {
        while !Task.isCancelled {
            await refresh()
            try? await Task.sleep(nanoseconds: isReachable ? 15_000_000_000 : 5_000_000_000)
        }
    }

    func refresh() async {
        struct Tags: Decodable { let models: [Model] }
        do {
            var req = URLRequest(url: baseURL.appendingPathComponent("api/tags"))
            req.timeoutInterval = 3
            let (data, response) = try await session.data(for: req)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                self.isReachable = false; return
            }
            let tags = try JSONDecoder().decode(Tags.self, from: data)
            self.availableModels = tags.models.sorted { $0.size > $1.size }
            self.isReachable = true
            self.lastError = nil

            // Auto-eject known problematic models on every refresh:
            // - Certain custom fine-tunes leak their fine-tuned persona even with a
            //   strong system prompt.
            // - Models under ~3B struggle with reliable tool calling.
            let bannedPrefixes = ["custom-", "private-"]
            let currentBanned = bannedPrefixes.contains { selectedModel.lowercased().hasPrefix($0) }
            let currentMissing = !availableModels.contains(where: { $0.name == selectedModel })
            if currentBanned || currentMissing, let best = pickBestModel() {
                selectedModel = best
            }
        } catch {
            self.isReachable = false
        }
    }

    /// Choose the best installed model for agent/tool use.
    /// Skips certain custom fine-tunes that would leak their own persona,
    /// prefers strong tool-callers, then falls back by size.
    private func pickBestModel() -> String? {
        let banned = ["custom-", "private-"]
        let usable = availableModels.filter { m in
            !banned.contains(where: { m.name.lowercased().hasPrefix($0) })
        }
        // Order matters: devstral & qwen3.6 emit native tool_calls; qwen2.5-coder
        // often stuffs them into content; llama3.2 is worst. Prefer natively-good ones.
        let prefs = ["devstral", "qwen3.6", "qwen2.5-coder", "hermes", "llama3.1", "llama3.2"]
        for p in prefs {
            if let m = usable.first(where: { $0.name.contains(p) }) { return m.name }
        }
        return usable.first?.name ?? availableModels.first?.name
    }

    // MARK: - Chat with tool calling

    struct ChatMessage: Codable {
        let role: String          // "system" | "user" | "assistant" | "tool"
        let content: String
        var tool_calls: [ToolCallReq]? = nil
        var tool_call_id: String? = nil
    }

    struct ToolCallReq: Codable {
        let function: FunctionCall
        /// Anthropic tool_use id (toolu_…) when the Claude backend is active;
        /// nil for Ollama, which doesn't issue call ids.
        var id: String? = nil
        struct FunctionCall: Codable {
            let name: String
            let arguments: ArgsJSON
        }
    }

    /// Ollama returns arguments as either a JSON object or a JSON-encoded string.
    /// This wrapper handles both shapes.
    struct ArgsJSON: Codable {
        let raw: [String: AnyCodable]
        init(_ dict: [String: AnyCodable]) { self.raw = dict }
        init(from decoder: Decoder) throws {
            let c = try decoder.singleValueContainer()
            if let dict = try? c.decode([String: AnyCodable].self) {
                self.raw = dict
            } else if let s = try? c.decode(String.self),
                      let data = s.data(using: .utf8),
                      let dict = try? JSONDecoder().decode([String: AnyCodable].self, from: data) {
                self.raw = dict
            } else {
                self.raw = [:]
            }
        }
        func encode(to encoder: Encoder) throws {
            var c = encoder.singleValueContainer()
            try c.encode(raw)
        }
        func string(_ key: String) -> String? { raw[key]?.value as? String }
    }

    struct ToolSpec: Encodable {
        let type: String = "function"
        let function: Function
        struct Function: Encodable {
            let name: String
            let description: String
            let parameters: Schema
        }
        struct Schema: Encodable {
            let type: String = "object"
            let properties: [String: Property]
            let required: [String]
        }
        struct Property: Encodable {
            let type: String
            let description: String
        }
    }

    private struct ChatRequest: Encodable {
        let model: String
        let messages: [ChatMessage]
        let stream: Bool
        let tools: [ToolSpec]?
        let options: [String: Double]?
    }

    private struct ChatResponse: Decodable {
        let message: ChatMessage
        let done: Bool
    }

    /// `model`: per-profile override; nil or "" falls back to the global picker.
    /// The override must actually be installed, otherwise it's ignored.
    func chat(messages: [ChatMessage], tools: [ToolSpec]? = nil,
              model: String? = nil, temperature: Double? = nil) async throws -> ChatMessage {
        var useModel = selectedModel
        if let m = model, !m.isEmpty, availableModels.contains(where: { $0.name == m }) {
            useModel = m
        }
        var req = URLRequest(url: baseURL.appendingPathComponent("api/chat"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body = ChatRequest(
            model: useModel,
            messages: messages,
            stream: false,
            tools: tools,
            options: ["temperature": temperature ?? 0.4]
        )
        req.httpBody = try JSONEncoder().encode(body)
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            let body = String(data: data, encoding: .utf8) ?? "(no body)"
            throw NSError(domain: "Ollama", code: (response as? HTTPURLResponse)?.statusCode ?? -1,
                          userInfo: [NSLocalizedDescriptionKey: body])
        }
        let decoded = try JSONDecoder().decode(ChatResponse.self, from: data)
        return Self.rescueContentToolCalls(decoded.message)
    }

    /// Streaming variant: NDJSON chunks from /api/chat. `onDelta` receives the
    /// accumulated content so far (not just the delta) on every chunk, on the
    /// main actor. Returns the fully assembled message (tool-call rescue applied).
    func chatStreaming(messages: [ChatMessage], tools: [ToolSpec]? = nil,
                       model: String? = nil, temperature: Double? = nil,
                       onDelta: @escaping (String) -> Void) async throws -> ChatMessage {
        var useModel = selectedModel
        if let m = model, !m.isEmpty, availableModels.contains(where: { $0.name == m }) {
            useModel = m
        }
        var req = URLRequest(url: baseURL.appendingPathComponent("api/chat"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body = ChatRequest(
            model: useModel,
            messages: messages,
            stream: true,
            tools: tools,
            options: ["temperature": temperature ?? 0.4]
        )
        req.httpBody = try JSONEncoder().encode(body)

        let (bytes, response) = try await session.bytes(for: req)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            var errBody = ""
            for try await line in bytes.lines { errBody += line }
            throw NSError(domain: "Ollama", code: (response as? HTTPURLResponse)?.statusCode ?? -1,
                          userInfo: [NSLocalizedDescriptionKey: errBody.isEmpty ? "(no body)" : errBody])
        }

        var content = ""
        var calls: [ToolCallReq] = []
        for try await line in bytes.lines {
            guard let data = line.data(using: .utf8),
                  let chunk = try? JSONDecoder().decode(ChatResponse.self, from: data) else { continue }
            if !chunk.message.content.isEmpty {
                content += chunk.message.content
                onDelta(content)
            }
            if let tc = chunk.message.tool_calls, !tc.isEmpty {
                calls.append(contentsOf: tc)
            }
            if chunk.done { break }
        }
        let assembled = ChatMessage(role: "assistant", content: content,
                                    tool_calls: calls.isEmpty ? nil : calls,
                                    tool_call_id: nil)
        return Self.rescueContentToolCalls(assembled)
    }

    /// Some Ollama models (qwen2.5-coder, llama3.2) emit tool calls as JSON in the
    /// `content` field instead of the native `tool_calls` array. If we see that
    /// pattern and no native tool_calls, rewrite the message so the agent loop
    /// treats it as a proper tool call.
    static func rescueContentToolCalls(_ msg: ChatMessage) -> ChatMessage {
        if let existing = msg.tool_calls, !existing.isEmpty { return msg }
        let content = msg.content.trimmingCharacters(in: .whitespacesAndNewlines)
        guard content.hasPrefix("{"), content.contains("\"name\"") else { return msg }
        guard let data = content.data(using: .utf8) else { return msg }

        // Try common shapes: {"name":"X","arguments":{...}} or {"name":"X","parameters":{...}}
        if let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let name = obj["name"] as? String {
            let argsAny = obj["arguments"] ?? obj["parameters"] ?? [:]
            var args: [String: AnyCodable] = [:]
            if let dict = argsAny as? [String: Any] {
                args = dict.mapValues { AnyCodable($0) }
            }
            let call = ToolCallReq(function: .init(name: name, arguments: ArgsJSON(args)))
            var rewritten = msg
            rewritten.tool_calls = [call]
            rewritten = ChatMessage(role: msg.role, content: "", tool_calls: [call],
                                    tool_call_id: msg.tool_call_id)
            return rewritten
        }
        return msg
    }
}

// MARK: - Tiny AnyCodable for JSON args

struct AnyCodable: Codable {
    let value: Any
    init(_ value: Any) { self.value = value }
    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self.value = NSNull(); return }
        if let v = try? c.decode(Bool.self)   { self.value = v; return }
        if let v = try? c.decode(Int.self)    { self.value = v; return }
        if let v = try? c.decode(Double.self) { self.value = v; return }
        if let v = try? c.decode(String.self) { self.value = v; return }
        if let v = try? c.decode([AnyCodable].self) { self.value = v.map(\.value); return }
        if let v = try? c.decode([String: AnyCodable].self) {
            self.value = v.mapValues(\.value); return
        }
        self.value = NSNull()
    }
    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch value {
        case let v as Bool:   try c.encode(v)
        case let v as Int:    try c.encode(v)
        case let v as Double: try c.encode(v)
        case let v as String: try c.encode(v)
        case let v as [Any]:  try c.encode(v.map(AnyCodable.init))
        case let v as [String: Any]: try c.encode(v.mapValues(AnyCodable.init))
        default: try c.encodeNil()
        }
    }
}
