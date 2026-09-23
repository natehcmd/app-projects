import Foundation

struct ToolCall: Identifiable, Equatable, Codable {
    enum Status: String, Codable { case running, completed, failed }

    var id = UUID()
    var tool: String
    var detail: String
    var status: Status = .completed
    var timestamp = Date()
    /// Set when this call originated from a `claude` CLI subprocess event
    /// (its `tool_use`/`tool_result` block id) so a later event can find and
    /// update this exact entry instead of assuming serial execution.
    var cliID: String? = nil

    var timeLabel: String {
        let f = DateFormatter()
        f.dateFormat = "HH:mm:ss"
        return f.string(from: timestamp)
    }
}
