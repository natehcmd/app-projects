import Foundation

/// Wire protocol between the Mac app (server, see Services/RemoteServer.swift
/// — Mac-only) and the iOS remote-control app (client, see
/// HandsAIMobile/RemoteAgentClient.swift). Plain Codable structs, no AppKit/
/// UIKit — this file is shared verbatim between both targets.

/// Phone → Mac. The very first frame on a connection is also treated as the
/// auth check (its `token` is compared against the Mac's stored token) even
/// before `text` is acted on.
struct RemoteRequest: Codable {
    var type: String = "message"
    var text: String = ""
    var token: String = ""
    /// Per-message override of which backend/model answers this one message —
    /// "ollama" / "claude" / "claude-cli". Nil means "use whatever's set in
    /// Settings on the Mac" (the iOS app's current behavior, unchanged).
    var engine: String? = nil
    var model: String? = nil
    /// Run one read-only tool directly (no chat turn) — how Command Center's
    /// Life HQ reads Calendar and Reminders through Hammond's existing
    /// permissions. Only names in RemoteServer's allow-list are honoured.
    var tool: String? = nil
    /// Only meaningful when `type == "permission"`: the `PermissionDenial.id`
    /// the decision below applies to.
    var id: String? = nil
    /// Only meaningful when `type == "permission"`: "once" | "always" | "deny".
    var decision: String? = nil

    enum CodingKeys: String, CodingKey {
        case type, text, token, engine, model, tool, id, decision
    }

    init(type: String = "message", text: String = "", token: String, engine: String? = nil,
         model: String? = nil, tool: String? = nil, id: String? = nil, decision: String? = nil) {
        self.type = type
        self.text = text
        self.token = token
        self.engine = engine
        self.model = model
        self.tool = tool
        self.id = id
        self.decision = decision
    }

    /// Custom decode (rather than the synthesized one) so a lean payload
    /// like `{"type":"permission","token":"…","id":"…","decision":"once"}` —
    /// no `text` key at all — still decodes instead of failing: synthesized
    /// `Decodable` would require every non-Optional property's key to be
    /// present, which a permission-decision frame (sent by the Command
    /// Center Chat tab and HandsAIMobile alike) has no reason to include.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        type = try c.decodeIfPresent(String.self, forKey: .type) ?? "message"
        text = try c.decodeIfPresent(String.self, forKey: .text) ?? ""
        token = try c.decodeIfPresent(String.self, forKey: .token) ?? ""
        engine = try c.decodeIfPresent(String.self, forKey: .engine)
        model = try c.decodeIfPresent(String.self, forKey: .model)
        tool = try c.decodeIfPresent(String.self, forKey: .tool)
        id = try c.decodeIfPresent(String.self, forKey: .id)
        decision = try c.decodeIfPresent(String.self, forKey: .decision)
    }
}

struct ChatHistoryItem: Codable {
    var role: String
    var text: String
}

/// A tool call Claude Code's CLI silently refused because it wasn't on the
/// `claudeCLI.allowedTools` allowlist (see ClaudeCLIClient's parsing of the
/// CLI's `result` event's `permission_denials`). Surfaced to the operator —
/// natively and over the Remote socket — as an Allow once / Always allow /
/// Deny card instead of just vanishing.
///
/// `rule` is the exact allow-rule string ("Bash(ls -la /tmp)", "Write",
/// "WebFetch(domain:example.com)") that `decision: .always` appends to the
/// allowlist — always an exact match, never a wildcard, so "always" only
/// ever grants that one specific thing, not a whole class of commands.
struct PermissionDenial: Identifiable, Equatable, Codable {
    /// The CLI's `tool_use_id` for the refused call — stable per denial, and
    /// what a decision (local or remote) targets.
    var id: String
    /// The CLI tool name, e.g. "Bash", "Write", "WebFetch".
    var tool: String
    /// Human-readable summary: the exact command for Bash, the path for file
    /// tools, otherwise the tool name or whatever detail is available.
    var summary: String
    /// Exact allow-rule string (see above).
    var rule: String
    /// True when `summary`/the command matches a destructive pattern (rm,
    /// mv, chmod, sudo, curl|sh, git push/reset, >, dd, kill, defaults
    /// write, osascript) — UI should require a second confirmation before
    /// "always allow"-ing it.
    var risky: Bool
}

/// Mac → phone. One event per `AgentStore` change (see RemoteServer's
/// Combine subscriptions) — mirrors the same four signals the Mac's own
/// ChatView/ToolFeedView/OrbView already bind to, just serialized.
struct RemoteEvent: Codable {
    enum Kind: String, Codable {
        case delta      // liveReply changed — `text` is the accumulated reply so far
        case toolCalls  // the tool feed changed — `toolCalls` is the full current list
        case final      // a completed assistant message was appended — `text` is set
        case user       // a user message was sent/appended — `text` is set
        case history    // conversation transcript snapshot — `history` is set
        case state      // AgentState changed — `state` is set
        case error      // auth failure or server-side problem — `text` is set
        case toolResult // answer to a request's `tool` — `tool` + `text` are set
        case permission // pending permission denials changed — `denials` is set
    }
    var type: Kind
    var text: String? = nil
    var tool: String? = nil
    var history: [ChatHistoryItem]? = nil
    /// Full snapshot, not a diff — simpler and avoids missed-update edge
    /// cases (e.g. the Claude CLI backend can update an entry that isn't at
    /// index 0) than trying to forward individual add/update events.
    var toolCalls: [ToolCall]? = nil
    var state: AgentState? = nil
    /// Full snapshot of `AgentStore.pendingDenials`, same "snapshot not a
    /// diff" rationale as `toolCalls` above.
    var denials: [PermissionDenial]? = nil
}
