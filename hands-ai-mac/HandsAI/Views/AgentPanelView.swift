import SwiftUI

struct AgentPanelView: View {
    @EnvironmentObject var agent: AgentStore
    @EnvironmentObject var voice: VoiceService

    /// While a reply streams in, show its tail instead of the static caption.
    private var captionText: String {
        if !agent.liveReply.isEmpty {
            return String(agent.liveReply.suffix(220))
        }
        return agent.state.caption.isEmpty ? "Speaking…" : agent.state.caption
    }

    var body: some View {
        VStack(spacing: 14) {
            Spacer(minLength: 8)

            OrbView(state: agent.state)
                .onTapGesture { voice.toggleListening() }
                .contextMenu {
                    Button("Run demo simulation") { agent.demoSimulate() }
                    Button("Reset") { agent.state = .idle }
                }

            Text(captionText)
                .font(.system(size: 14, weight: .medium, design: .rounded))
                .foregroundStyle(.primary.opacity(0.92))
                .multilineTextAlignment(.center)
                .textSelection(.enabled)
                .lineLimit(4)
                .frame(maxWidth: 360)
                .animation(.easeInOut(duration: 0.25), value: agent.state)

            if voice.isListening || !voice.lastTranscript.isEmpty {
                Text(voice.lastTranscript.isEmpty ? "Listening…" : voice.lastTranscript)
                    .font(.system(size: 12, design: .rounded))
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 6)
                    .background(
                        Capsule().fill(Color.white.opacity(0.06))
                    )
                    .transition(.opacity)
            }

            DaemonBanner()
                .padding(.horizontal, 20)

            ToolFeedView()
                .padding(.horizontal, 20)
                .padding(.top, 6)

            HStack(spacing: 10) {
                MicButton()
                InputField()
            }
            .padding(.horizontal, 18)
            .padding(.bottom, 14)
        }
    }
}

private struct MicButton: View {
    @EnvironmentObject var voice: VoiceService

    var body: some View {
        Button {
            voice.toggleListening()
        } label: {
            ZStack {
                Circle()
                    .fill(voice.isListening ? Color.red.opacity(0.85) : Color.white.opacity(0.10))
                    .frame(width: 36, height: 36)
                    .overlay(
                        Circle().strokeBorder(.white.opacity(0.18), lineWidth: 1)
                    )
                Image(systemName: voice.isListening ? "stop.fill" : "mic.fill")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(.white)
            }
        }
        .buttonStyle(.plain)
        .help(voice.isListening ? "Stop listening" : "Start listening")
    }
}

private struct InputField: View {
    @EnvironmentObject var agent: AgentStore

    var body: some View {
        HStack {
            TextField("Speak or type, sir…", text: $agent.input)
                .textFieldStyle(.plain)
                .font(.system(size: 13, design: .rounded))
                .onSubmit { agent.send(agent.input) }
            Button { agent.send(agent.input) } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 20))
                    .foregroundStyle(.white.opacity(0.85))
            }
            .buttonStyle(.plain)
            .disabled(agent.input.trimmingCharacters(in: .whitespaces).isEmpty)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Color.white.opacity(0.06))
                .overlay(
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .strokeBorder(.white.opacity(0.10), lineWidth: 1)
                )
        )
    }
}
