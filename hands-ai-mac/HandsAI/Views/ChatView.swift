import SwiftUI

struct ChatView: View {
    @EnvironmentObject var agent: AgentStore
    @EnvironmentObject var voice: VoiceService
    @AppStorage("chat.viewMode") private var plainMode: Bool = false

    var body: some View {
        VStack(spacing: 0) {
            ChatToolbar(plainMode: $plainMode, transcript: agent.transcript)

            if plainMode {
                SelectableConversation(messages: agent.transcript)
                    .background(Color.black.opacity(0.18))
            } else {
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 8) {
                            if agent.transcript.isEmpty {
                                VStack(spacing: 8) {
                                    Text("No conversation yet.")
                                        .font(.system(size: 12, design: .rounded))
                                        .foregroundStyle(.tertiary)
                                    Text("Try: \"what's my CPU at, sir?\"")
                                        .font(.system(size: 11, design: .monospaced))
                                        .foregroundStyle(.quaternary)
                                }
                                .padding(.vertical, 60)
                            } else {
                                ForEach(agent.transcript) { msg in
                                    MessageBubble(message: msg)
                                        .id(msg.id)
                                }
                            }
                            if !agent.liveReply.isEmpty {
                                LiveBubble(text: agent.liveReply)
                                    .id("live-reply")
                            }
                        }
                        .padding(14)
                    }
                    .onChange(of: agent.transcript.count) { _, _ in
                        if let last = agent.transcript.last {
                            withAnimation(.easeOut(duration: 0.2)) {
                                proxy.scrollTo(last.id, anchor: .bottom)
                            }
                        }
                    }
                    .onChange(of: agent.liveReply) { _, new in
                        if !new.isEmpty {
                            proxy.scrollTo("live-reply", anchor: .bottom)
                        }
                    }
                }
            }

            DaemonBanner()
                .padding(.horizontal, 14)
                .padding(.top, 4)

            VoiceQualityBanner()
                .padding(.horizontal, 14)

            ChatInput()
                .padding(14)
        }
        .onReceive(NotificationCenter.default.publisher(for: .speakMessage)) { note in
            if let text = note.object as? String { voice.speak(text) }
        }
    }
}

private struct ChatToolbar: View {
    @Binding var plainMode: Bool
    let transcript: [Message]

    var body: some View {
        HStack(spacing: 8) {
            Picker("", selection: $plainMode) {
                Text("Bubbles").tag(false)
                Text("Plain").tag(true)
            }
            .pickerStyle(.segmented)
            .frame(width: 160)
            .help("Plain mode lets you drag-select across the whole conversation.")

            Spacer()

            Button {
                let text = transcript.map { ($0.role == .user ? "You: " : "Hands: ") + $0.text }
                    .joined(separator: "\n\n")
                NSPasteboard.general.clearContents()
                NSPasteboard.general.setString(text, forType: .string)
            } label: {
                Label("Copy all", systemImage: "doc.on.doc")
                    .font(.system(size: 11))
            }
            .controlSize(.small)
            .disabled(transcript.isEmpty)
        }
        .padding(.horizontal, 14)
        .padding(.top, 10)
        .padding(.bottom, 6)
    }
}

struct DaemonBanner: View {
    @EnvironmentObject var ollama: OllamaClient

    var body: some View {
        if !ollama.isReachable {
            HStack(alignment: .center, spacing: 10) {
                Image(systemName: "cube.transparent")
                    .font(.system(size: 14))
                    .foregroundStyle(.orange)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Ollama not running")
                        .font(.system(size: 12, weight: .semibold, design: .rounded))
                    Text("Start Ollama in a terminal: `ollama serve` — then this banner will disappear.")
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
                Spacer()
                Button("Retry") {
                    Task { await ollama.refresh() }
                }
                .controlSize(.small)
            }
            .padding(10)
            .background(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(Color.orange.opacity(0.10))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .strokeBorder(Color.orange.opacity(0.30), lineWidth: 1)
                    )
            )
        }
    }
}

struct VoiceQualityBanner: View {
    @EnvironmentObject var voice: VoiceService
    @State private var dismissed = false

    var body: some View {
        if voice.hasOnlyDefaultVoices && !dismissed {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: "waveform.badge.exclamationmark")
                    .font(.system(size: 16))
                    .foregroundStyle(.yellow)
                VStack(alignment: .leading, spacing: 4) {
                    Text("Voice quality is low")
                        .font(.system(size: 12, weight: .semibold, design: .rounded))
                    Text("Install Daniel (Premium) for the proper British butler voice. Takes ~1 min.")
                        .font(.system(size: 11, design: .rounded))
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                    HStack(spacing: 6) {
                        Button("Open System Settings") {
                            if let url = URL(string: "x-apple.systempreferences:com.apple.preference.universalaccess?Spoken_Content") {
                                NSWorkspace.shared.open(url)
                            }
                        }
                        .controlSize(.small)
                        Button("Dismiss") { dismissed = true }
                            .controlSize(.small)
                            .buttonStyle(.borderless)
                            .foregroundStyle(.secondary)
                    }
                }
                Spacer()
            }
            .padding(10)
            .background(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(Color.yellow.opacity(0.10))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .strokeBorder(Color.yellow.opacity(0.25), lineWidth: 1)
                    )
            )
        }
    }
}

/// Assistant text still streaming in — same look as an assistant bubble,
/// with a subtle pulsing cursor dot.
private struct LiveBubble: View {
    let text: String
    @State private var pulse = false

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                HStack(alignment: .bottom, spacing: 6) {
                    Text(text)
                        .font(.system(size: 13, design: .rounded))
                    Circle()
                        .fill(Color.white.opacity(pulse ? 0.15 : 0.65))
                        .frame(width: 7, height: 7)
                        .animation(.easeInOut(duration: 0.5).repeatForever(autoreverses: true),
                                   value: pulse)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .fill(Color.white.opacity(0.06))
                )
            }
            Spacer(minLength: 40)
        }
        .onAppear { pulse = true }
    }
}

private struct MessageBubble: View {
    let message: Message

    var body: some View {
        HStack {
            if message.role == .user { Spacer(minLength: 40) }
            VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 2) {
                Text(message.text)
                    .font(.system(size: 13, design: .rounded))
                    .textSelection(.enabled)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .fill(message.role == .user
                                  ? Color.accentColor.opacity(0.30)
                                  : Color.white.opacity(0.06))
                    )
                    .foregroundStyle(.primary)
                    .contextMenu {
                        Button("Copy") {
                            NSPasteboard.general.clearContents()
                            NSPasteboard.general.setString(message.text, forType: .string)
                        }
                        Button("Speak again") {
                            NotificationCenter.default.post(name: .speakMessage, object: message.text)
                        }
                    }
            }
            if message.role == .assistant { Spacer(minLength: 40) }
        }
    }
}

extension Notification.Name {
    static let speakMessage = Notification.Name("HandsAI.speakMessage")
}

private struct ChatInput: View {
    @EnvironmentObject var agent: AgentStore
    @EnvironmentObject var voice: VoiceService

    var body: some View {
        HStack(spacing: 10) {
            Button { voice.toggleListening() } label: {
                Image(systemName: voice.isListening ? "stop.circle.fill" : "mic.circle.fill")
                    .font(.system(size: 22))
                    .foregroundStyle(voice.isListening ? .red : .white.opacity(0.7))
            }
            .buttonStyle(.plain)

            TextField("Ask anything…", text: $agent.input)
                .textFieldStyle(.plain)
                .font(.system(size: 13, design: .rounded))
                .onSubmit { agent.send(agent.input) }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .fill(Color.white.opacity(0.06))
                        .overlay(
                            RoundedRectangle(cornerRadius: 12, style: .continuous)
                                .strokeBorder(.white.opacity(0.10), lineWidth: 1)
                        )
                )

            Button { agent.send(agent.input) } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 22))
                    .foregroundStyle(.white.opacity(0.85))
            }
            .buttonStyle(.plain)
            .disabled(agent.input.trimmingCharacters(in: .whitespaces).isEmpty)
        }
    }
}
