import Foundation

struct ToolCall: Identifiable, Equatable {
    enum Status: String { case running, completed, failed }

    var id = UUID()
    var tool: String
    var detail: String
    var status: Status = .completed
    var timestamp = Date()

    var timeLabel: String {
        let f = DateFormatter()
        f.dateFormat = "HH:mm:ss"
        return f.string(from: timestamp)
    }
}
