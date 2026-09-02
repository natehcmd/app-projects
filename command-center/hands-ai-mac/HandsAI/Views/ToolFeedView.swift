import SwiftUI

/// Portable — no AppKit, no Mac-only service types. Takes `toolCalls`
/// directly rather than reading an `AgentStore` from the environment, so it's
/// shared as-is with the iOS remote-control target (bound to
/// `RemoteAgentClient.toolCalls` there instead).
struct ToolFeedView: View {
    let toolCalls: [ToolCall]

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Activity")
                    .font(.system(size: 10, weight: .semibold, design: .rounded))
                    .foregroundStyle(.secondary)
                    .textCase(.uppercase)
                Spacer()
                if !toolCalls.isEmpty {
                    Text("\(toolCalls.count)")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(.tertiary)
                }
            }
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 4) {
                    if toolCalls.isEmpty {
                        Text("No actions yet. Try \"run the demo simulation.\"")
                            .font(.system(size: 11, design: .rounded))
                            .foregroundStyle(.tertiary)
                            .padding(.vertical, 8)
                    } else {
                        ForEach(toolCalls.prefix(7)) { call in
                            ToolRow(call: call)
                                .transition(.opacity.combined(with: .move(edge: .top)))
                        }
                    }
                }
                .textSelection(.enabled)
            }
            .frame(height: 120)
        }
        .padding(12)
        .glassCard(radius: 14)
    }
}

private struct ToolRow: View {
    let call: ToolCall

    var body: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(color)
                .frame(width: 6, height: 6)
            Text(call.tool)
                .font(.system(size: 11, weight: .semibold, design: .monospaced))
                .foregroundStyle(.primary.opacity(0.9))
            Text(call.detail)
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(.secondary)
                .lineLimit(1)
                .truncationMode(.middle)
            Spacer(minLength: 4)
            Text(call.timeLabel)
                .font(.system(size: 10, design: .monospaced))
                .foregroundStyle(.tertiary)
        }
        .padding(.vertical, 2)
    }

    private var color: Color {
        switch call.status {
        case .running:   return .yellow
        case .completed: return .green
        case .failed:    return .red
        }
    }
}
