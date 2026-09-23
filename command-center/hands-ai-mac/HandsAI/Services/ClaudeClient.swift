import Foundation
import SwiftUI

/// Direct client for the Anthropic Claude API (raw HTTP — no SDK for Swift).
/// Speaks the Messages API with SSE streaming and tool use, converting to and
/// from the app's internal message shape (OllamaClient.ChatMessage) so the
/// agent loop doesn't care which backend is active.
@MainActor
final class ClaudeClient: ObservableObject {
    @AppStorage("claude.apiKey") var apiKey: String = ""
    @AppStorage("claude.model") var selectedModel: String = "claude-opus-4-8"

    static let models: [(id: String, label: String)] = [
        ("claude-opus-4-8", "Opus 4.8 — most capable"),
        ("claude-sonnet-5", "Sonnet 5 — fast + smart"),
        ("claude-haiku-4-5", "Haiku 4.5 — fastest"),
    ]

    var isConfigured: Bool { !apiKey.trimmingCharacters(in: .whitespaces).isEmpty }

    private let session: URLSession = {
        let cfg = URLSessionConfiguration.ephemeral
        cfg.timeoutIntervalForRequest = 600
        return URLSession(configuration: cfg)
    }()

    // MARK: - Request encoding (Anthropic wire format)

    private struct AnthropicRequest: Encodable {
        let model: String
        let max_tokens: Int
        let system: String?
        let messages: [AnthropicMessage]
        let tools: [AnthropicTool]?
        let stream: Bool
    }

    private struct AnthropicMessage: Encodable {
        let role: String                 // "user" | "assistant"
        let content: [ContentBlock]
    }

    private enum ContentBlock: Encodable {
        case text(String)
        case toolUse(id: String, name: String, input: [String: AnyCodable])
        case toolResult(toolUseID: String, content: String)

        func encode(to encoder: Encoder) throws {
            var c = encoder.container(keyedBy: DynamicKey.self)
            switch self {
            case .text(let t):
                try c.encode("text", forKey: .init("type"))
                try c.encode(t, forKey: .init("text"))
            case .toolUse(let id, let name, let input):
                try c.encode("tool_use", forKey: .init("type"))
                try c.encode(id, forKey: .init("id"))
                try c.encode(name, forKey: .init("name"))
                try c.encode(input, forKey: .init("input"))
            case .toolResult(let toolUseID, let content):
                try c.encode("tool_result", forKey: .init("type"))
                try c.encode(toolUseID, forKey: .init("tool_use_id"))
                try c.encode(content, forKey: .init("content"))
            }
        }
    }

    private struct DynamicKey: CodingKey {
        var stringValue: String
        var intValue: Int? { nil }
        init(_ s: String) { stringValue = s }
        init?(stringValue: String) { self.stringValue = stringValue }
        init?(intValue: Int) { nil }
    }

    private struct AnthropicTool: Encodable {
        let name: String
        let description: String
        let input_schema: OllamaClient.ToolSpec.Schema
    }

    // MARK: - Message conversion

    /// Convert the app's internal transcript into an Anthropic request body.
    /// The internal shape is Ollama-flavored: a "system" message, flat user/
    /// assistant turns, assistant tool_calls, and "tool" role results.
    private static func convert(messages: [OllamaClient.ChatMessage])
        -> (system: String?, converted: [AnthropicMessage]) {
        var system: String? = nil
        var out: [AnthropicMessage] = []

        for m in messages {
            switch m.role {
            case "system":
                system = (system.map { $0 + "\n\n" } ?? "") + m.content
            case "user":
                out.append(.init(role: "user", content: [.text(m.content)]))
            case "assistant":
                var blocks: [ContentBlock] = []
                if !m.content.isEmpty { blocks.append(.text(m.content)) }
                for (i, call) in (m.tool_calls ?? []).enumerated() {
                    blocks.append(.toolUse(
                        id: call.id ?? "toolu_local_\(out.count)_\(i)",
                        name: call.function.name,
                        input: call.function.arguments.raw
                    ))
                }
                if !blocks.isEmpty {
                    out.append(.init(role: "assistant", content: blocks))
                }
            case "tool":
                let block = ContentBlock.toolResult(
                    toolUseID: m.tool_call_id ?? "toolu_unknown",
                    content: m.content
                )
                // Parallel tool results must share ONE user message.
                if let last = out.last, last.role == "user",
                   last.content.allSatisfy({ if case .toolResult = $0 { return true }; return false }) {
                    out[out.count - 1] = .init(role: "user", content: last.content + [block])
                } else {
                    out.append(.init(role: "user", content: [block]))
                }
            default:
                break
            }
        }
        return (system, out)
    }

    // MARK: - SSE streaming chat

    /// Streams a reply, invoking onDelta with the accumulated text so far.
    /// Returns the assembled message in the app's internal shape (tool calls
    /// carry their Anthropic tool_use IDs for the result round-trip).
    func chatStreaming(messages: [OllamaClient.ChatMessage],
                       tools: [OllamaClient.ToolSpec],
                       model: String? = nil,
                       onDelta: @escaping (String) -> Void) async throws -> OllamaClient.ChatMessage {
        let key = apiKey.trimmingCharacters(in: .whitespaces)
        guard !key.isEmpty else {
            throw NSError(domain: "Claude", code: 401,
                          userInfo: [NSLocalizedDescriptionKey: "No Claude API key set (Settings → Backend)."])
        }

        let (system, converted) = Self.convert(messages: messages)
        let body = AnthropicRequest(
            model: model?.isEmpty == false ? model! : selectedModel,
            max_tokens: 8192,
            system: system,
            messages: converted,
            tools: tools.map { AnthropicTool(name: $0.function.name,
                                             description: $0.function.description,
                                             input_schema: $0.function.parameters) },
            stream: true
        )

        var req = URLRequest(url: URL(string: "https://api.anthropic.com/v1/messages")!)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue(key, forHTTPHeaderField: "x-api-key")
        req.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
        req.httpBody = try JSONEncoder().encode(body)

        let (bytes, response) = try await session.bytes(for: req)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            var errBody = ""
            for try await line in bytes.lines { errBody += line }
            let msg = Self.extractAPIError(errBody) ?? errBody
            throw NSError(domain: "Claude", code: (response as? HTTPURLResponse)?.statusCode ?? -1,
                          userInfo: [NSLocalizedDescriptionKey: msg])
        }

        // SSE: accumulate text deltas + tool_use blocks (input arrives as partial JSON).
        var text = ""
        var toolCalls: [OllamaClient.ToolCallReq] = []
        var pendingTool: (index: Int, id: String, name: String, json: String)? = nil
        var stopReason: String? = nil

        for try await line in bytes.lines {
            guard line.hasPrefix("data: ") else { continue }
            let payload = String(line.dropFirst(6))
            guard let data = payload.data(using: .utf8),
                  let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let type = obj["type"] as? String else { continue }

            switch type {
            case "content_block_start":
                if let block = obj["content_block"] as? [String: Any],
                   (block["type"] as? String) == "tool_use",
                   let id = block["id"] as? String,
                   let name = block["name"] as? String {
                    pendingTool = (obj["index"] as? Int ?? 0, id, name, "")
                }
            case "content_block_delta":
                if let delta = obj["delta"] as? [String: Any] {
                    if let t = delta["text"] as? String {
                        text += t
                        onDelta(text)
                    } else if let pj = delta["partial_json"] as? String {
                        pendingTool?.json += pj
                    }
                }
            case "content_block_stop":
                if let tool = pendingTool {
                    var args: [String: AnyCodable] = [:]
                    if let d = tool.json.data(using: .utf8),
                       let dict = try? JSONDecoder().decode([String: AnyCodable].self, from: d) {
                        args = dict
                    }
                    toolCalls.append(.init(
                        function: .init(name: tool.name, arguments: OllamaClient.ArgsJSON(args)),
                        id: tool.id
                    ))
                    pendingTool = nil
                }
            case "message_delta":
                if let delta = obj["delta"] as? [String: Any] {
                    stopReason = delta["stop_reason"] as? String
                }
            case "error":
                let msg = (obj["error"] as? [String: Any])?["message"] as? String ?? "stream error"
                throw NSError(domain: "Claude", code: -2,
                              userInfo: [NSLocalizedDescriptionKey: msg])
            default:
                break
            }
        }

        if stopReason == "refusal" {
            text = text.isEmpty ? "I can't help with that one, sir." : text
            toolCalls = []
        }
        return OllamaClient.ChatMessage(role: "assistant", content: text,
                                        tool_calls: toolCalls.isEmpty ? nil : toolCalls,
                                        tool_call_id: nil)
    }

    private static func extractAPIError(_ raw: String) -> String? {
        guard let data = raw.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let err = obj["error"] as? [String: Any] else { return nil }
        return err["message"] as? String
    }
}
