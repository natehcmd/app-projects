import SwiftUI

/// The Mac app's real, normal window — a plain resizable window (not a
/// borderless floating panel) so it behaves like an ordinary Mac app
/// alongside the menu-bar icon. Binds directly to the same `AgentStore`
/// instance RemoteServer drives from Command Center/iOS, so a message sent
/// here shows up there too and vice versa.
struct ChatWindowView: View {
    @EnvironmentObject var agent: AgentStore
    @FocusState private var inputFocused: Bool

    var body: some View {
        ZStack {
            Theme.bg.ignoresSafeArea()
            VStack(spacing: 0) {
                header
                HStack(alignment: .top, spacing: 16) {
                    orbColumn
                    ToolFeedView(toolCalls: agent.toolCalls)
                }
                .padding(.horizontal, 20)
                .padding(.top, 4)

                Divider().overlay(Theme.glassBrd).padding(.top, 16)

                transcript

                inputBar
            }
        }
        .frame(minWidth: 640, minHeight: 520)
        .onAppear { inputFocused = true }
    }

    private var header: some View {
        HStack {
            Text("Hammond")
                .font(.system(size: 16, weight: .semibold, design: .rounded))
                .foregroundStyle(Theme.ink)
            Spacer()
            Text(agent.activeProvider)
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(Theme.inkDim)
                .padding(.horizontal, 8).padding(.vertical, 3)
                .glassCard(radius: 8)
        }
        .padding(16)
    }

    private var orbColumn: some View {
        VStack(spacing: 8) {
            OrbView(state: agent.state)
            Text(agent.state.caption.isEmpty ? "Ready." : agent.state.caption)
                .font(.system(size: 12, design: .rounded))
                .foregroundStyle(Theme.inkDim)
                .multilineTextAlignment(.center)
                .frame(width: 200)
        }
    }

    private var transcript: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 10) {
                    if agent.transcript.isEmpty && agent.liveReply.isEmpty {
                        Text("Say something below — this runs the same agent Command Center and the iOS app use.")
                            .font(.system(size: 12, design: .rounded))
                            .foregroundStyle(Theme.inkFaint)
                            .padding(.top, 24)
                            .frame(maxWidth: .infinity)
                    }
                    ForEach(agent.transcript) { MessageBubble(message: $0) }
                    if !agent.liveReply.isEmpty {
                        MessageBubble(message: Message(role: .assistant, text: agent.liveReply))
                            .id("live")
                    }
                }
                .padding(16)
            }
            .onChange(of: agent.transcript) { _, _ in
                withAnimation { proxy.scrollTo(agent.transcript.last?.id, anchor: .bottom) }
            }
            .onChange(of: agent.liveReply) { _, text in
                if !text.isEmpty { proxy.scrollTo("live", anchor: .bottom) }
            }
        }
    }

    private var inputBar: some View {
        HStack(spacing: 10) {
            TextField("Message Hammond…", text: $agent.input, axis: .vertical)
                .textFieldStyle(.plain)
                .font(.system(size: 13, design: .rounded))
                .padding(10)
                .glassCard(radius: 10)
                .focused($inputFocused)
                .lineLimit(1...4)
                .onSubmit(send)

            Button(action: send) {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 26))
                    .foregroundStyle(agent.input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                                      ? Theme.inkFaint : Theme.sky)
            }
            .buttonStyle(.plain)
            .disabled(agent.input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        }
        .padding(16)
    }

    private func send() {
        let text = agent.input
        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        agent.send(text)
    }
}

private struct MessageBubble: View {
    let message: Message

    var body: some View {
        HStack {
            if message.role == .assistant { EmptyView() } else { Spacer(minLength: 40) }
            Text(message.text)
                .font(.system(size: 13, design: .rounded))
                .foregroundStyle(Theme.ink)
                .padding(.horizontal, 12).padding(.vertical, 8)
                .background(
                    RoundedRectangle(cornerRadius: 14, style: .continuous)
                        .fill(message.role == .assistant ? Theme.glass : Theme.sky.opacity(0.18))
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 14, style: .continuous)
                        .strokeBorder(Theme.glassBrd, lineWidth: 1)
                )
                .textSelection(.enabled)
            if message.role == .assistant { Spacer(minLength: 40) } else { EmptyView() }
        }
    }
}

#Preview {
    ChatWindowView()
        .environmentObject(AgentStore())
        .frame(width: 700, height: 560)
}
