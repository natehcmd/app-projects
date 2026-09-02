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
    var text: String
    var token: String
    /// Per-message override of which backend/model answers this one message —
    /// "ollama" / "claude" / "claude-cli". Nil means "use whatever's set in
    /// Settings on the Mac" (the iOS app's current behavior, unchanged).
    var engine: String? = nil
    var model: String? = nil
}

struct ChatHistoryItem: Codable {
    var role: String
    var text: String
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
    }
    var type: Kind
    var text: String? = nil
    var history: [ChatHistoryItem]? = nil
    /// Full snapshot, not a diff — simpler and avoids missed-update edge
    /// cases (e.g. the Claude CLI backend can update an entry that isn't at
    /// index 0) than trying to forward individual add/update events.
    var toolCalls: [ToolCall]? = nil
    var state: AgentState? = nil
}
