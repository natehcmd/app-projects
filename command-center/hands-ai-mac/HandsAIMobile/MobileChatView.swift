import SwiftUI

/// The phone's main screen — deliberately simple for v1 (no voice, no
/// profile/skill switching, no port of the Mac's ChatView which relies on
/// NSPasteboard). Message list + live reply + tool feed + orb + text input,
/// all driven by `RemoteAgentClient` exactly the way the Mac's own views are
/// driven by `AgentStore`.
struct MobileChatView: View {
    @EnvironmentObject var remote: RemoteAgentClient
    @State private var showSettings = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                statusBar

                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 10) {
                            if remote.transcript.isEmpty {
                                Text("No conversation yet.")
                                    .font(.system(size: 13, design: .rounded))
                                    .foregroundStyle(.tertiary)
                                    .padding(.top, 40)
                                    .frame(maxWidth: .infinity)
                            }
                            ForEach(remote.transcript) { message in
                                bubble(for: message).id(message.id)
                            }
                            if !remote.liveReply.isEmpty {
                                bubbleContent(text: remote.liveReply, isUser: false)
                                    .id("live")
                            }
                        }
                        .padding(16)
                    }
                    .onChange(of: remote.transcript.count) { _, _ in
                        if let last = remote.transcript.last {
                            withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                        }
                    }
                    .onChange(of: remote.liveReply) { _, new in
                        if !new.isEmpty { proxy.scrollTo("live", anchor: .bottom) }
                    }
                }

                ToolFeedView(toolCalls: remote.toolCalls)
                    .padding(.horizontal, 16)

                inputBar
            }
            .background(Theme.bg.ignoresSafeArea())
            .navigationTitle("Hands AI")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    OrbView(state: remote.state)
                        .scaleEffect(0.22)
                        .frame(width: 44, height: 44)
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showSettings = true } label: {
                        Image(systemName: "gearshape")
                    }
                }
            }
            .sheet(isPresented: $showSettings) {
                ConnectionSettingsView()
            }
            .onAppear {
                if remote.connectionStatus == .disconnected { remote.connect() }
            }
        }
    }

    private var statusBar: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(statusColor)
                .frame(width: 7, height: 7)
            Text(statusText)
                .font(.system(size: 11, design: .rounded))
                .foregroundStyle(.secondary)
            Spacer()
            if case .failed = remote.connectionStatus {
                Button("Retry") { remote.connect() }
                    .font(.system(size: 11))
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 6)
    }

    private var statusColor: Color {
        switch remote.connectionStatus {
        case .connected:    return Theme.mint
        case .connecting:   return Theme.peach
        case .failed:       return Theme.alert
        case .disconnected: return .secondary
        }
    }

    private var statusText: String {
        switch remote.connectionStatus {
        case .connected:            return "Connected to \(remote.host)"
        case .connecting:           return "Connecting…"
        case .failed(let message):  return message
        case .disconnected:         return "Not connected"
        }
    }

    private func bubble(for message: Message) -> some View {
        bubbleContent(text: message.text, isUser: message.role == .user)
    }

    private func bubbleContent(text: String, isUser: Bool) -> some View {
        HStack {
            if isUser { Spacer(minLength: 40) }
            Text(text)
                .font(.system(size: 15, design: .rounded))
                .foregroundStyle(Theme.ink)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(
                    Group {
                        if isUser {
                            RoundedRectangle(cornerRadius: 16, style: .continuous)
                                .fill(Theme.mint.opacity(0.28))
                        } else {
                            RoundedRectangle(cornerRadius: 16, style: .continuous)
                                .fill(Theme.glass)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                                        .strokeBorder(Theme.glassBrd, lineWidth: 1)
                                )
                        }
                    }
                )
            if !isUser { Spacer(minLength: 40) }
        }
    }

    private var inputBar: some View {
        InputBar { text in remote.send(text) }
            .padding(16)
    }
}

private struct InputBar: View {
    let onSend: (String) -> Void
    @State private var text = ""

    var body: some View {
        HStack(spacing: 10) {
            TextField("Ask Hands AI…", text: $text, axis: .vertical)
                .font(.system(size: 15, design: .rounded))
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .glassCard(radius: 14)
            Button {
                let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !trimmed.isEmpty else { return }
                onSend(trimmed)
                text = ""
            } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 28))
                    .foregroundStyle(Theme.ink.opacity(0.85))
            }
            .disabled(text.trimmingCharacters(in: .whitespaces).isEmpty)
        }
    }
}
