import Foundation
import SwiftUI

/// Portable model — no AppKit, no Mac-only service types. Shared with the
/// iOS remote-control target as-is (see project.yml).
enum AgentState: Equatable, Codable {
    case idle
    case listening
    case thinking
    case reading(path: String)
    case writing(path: String)
    case editing(path: String)
    case bash(command: String)
    case web(url: String)
    case app(name: String)
    case skill(name: String)
    case speaking
    case error(message: String)

    var caption: String {
        switch self {
        case .idle:                return "Standing by, sir."
        case .listening:           return "Listening…"
        case .thinking:            return "Considering."
        case .reading(let p):      return "Reading \(URL(fileURLWithPath: p).lastPathComponent)."
        case .writing(let p):      return "Writing \(URL(fileURLWithPath: p).lastPathComponent)."
        case .editing(let p):      return "Editing \(URL(fileURLWithPath: p).lastPathComponent)."
        case .bash(let c):         return "Running: \(c.prefix(40))…"
        case .web(let u):          return "Fetching \(URL(string: u)?.host ?? u)."
        case .app(let n):          return "Working \(n)."
        case .skill(let n):        return "Using skill: \(n)."
        case .speaking:            return ""
        case .error(let m):        return "Holding, sir — \(m)"
        }
    }

    /// Pulls from the shared "nate-default" pastel palette (Theme.swift) —
    /// the same tones net-worth/my-apps/unified-os use — instead of ad hoc
    /// HSB values, so the orb reads as part of the same family of apps.
    var tint: Color {
        switch self {
        case .idle:        return Theme.sky
        case .listening:   return Theme.sky
        case .thinking:    return Theme.lav
        case .reading:     return Theme.peach
        case .writing:     return Theme.peach
        case .editing:     return Theme.rose
        case .bash:        return Theme.mint
        case .web:         return Theme.sky
        case .app:         return Theme.lav
        case .skill:       return Theme.lav
        case .speaking:    return Theme.sky
        case .error:       return Theme.alert
        }
    }

    var symbol: String {
        switch self {
        case .idle:        return "circle.dotted"
        case .listening:   return "waveform"
        case .thinking:    return "sparkles"
        case .reading:     return "doc.text"
        case .writing:     return "square.and.pencil"
        case .editing:     return "pencil.tip"
        case .bash:        return "terminal"
        case .web:         return "globe"
        case .app:         return "macwindow"
        case .skill:       return "book.closed"
        case .speaking:    return "waveform.circle.fill"
        case .error:       return "exclamationmark.triangle.fill"
        }
    }
}

struct Message: Identifiable, Equatable, Codable {
    enum Role: String, Codable { case user, assistant }
    let id: UUID
    let role: Role
    let text: String
    let timestamp: Date

    init(role: Role, text: String) {
        self.id = UUID()
        self.role = role
        self.text = text
        self.timestamp = Date()
    }
}
