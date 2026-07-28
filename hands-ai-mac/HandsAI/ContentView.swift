import SwiftUI

enum AppTab: String, CaseIterable, Identifiable {
    case agent = "Agent"
    case stats = "System"
    case chat  = "Chat"
    var id: String { rawValue }

    var symbol: String {
        switch self {
        case .agent: return "circle.hexagongrid.fill"
        case .stats: return "cpu"
        case .chat:  return "bubble.left.and.text.bubble.right"
        }
    }
}

struct ContentView: View {
    @EnvironmentObject var agent: AgentStore
    @EnvironmentObject var stats: StatsService
    @EnvironmentObject var ollama: OllamaClient
    @EnvironmentObject var voice: VoiceService
    @State private var tab: AppTab = .agent

    var body: some View {
        ZStack {
            VisualEffectView(material: .underWindowBackground, blendingMode: .behindWindow)
                .ignoresSafeArea()

            VStack(spacing: 0) {
                TitleBar(tab: $tab)
                Divider().opacity(0.4)

                Group {
                    switch tab {
                    case .agent: AgentPanelView()
                    case .stats: StatsView()
                    case .chat:  ChatView()
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .transition(.opacity.combined(with: .move(edge: .bottom)))

                StatusFooter()
            }
        }
        .frame(minWidth: 480, minHeight: 600)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .strokeBorder(.white.opacity(0.06), lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.45), radius: 30, x: 0, y: 12)
        .preferredColorScheme(.dark)
        .onAppear {
            voice.onFinalTranscript = { text in
                agent.send(text)
            }
        }
    }
}

private struct TitleBar: View {
    @Binding var tab: AppTab
    @EnvironmentObject var ollama: OllamaClient
    @EnvironmentObject var claude: ClaudeClient
    @EnvironmentObject var profiles: ProfileStore
    @EnvironmentObject var agent: AgentStore

    private var backendLabel: (text: String, ok: Bool) {
        if agent.activeProvider == "claude" {
            return ("claude · \(claude.selectedModel)", true)
        }
        return (ollama.isReachable ? "ollama · \(ollama.selectedModel)" : "ollama offline",
                ollama.isReachable)
    }

    var body: some View {
        HStack(spacing: 12) {
            TrafficLights()
            LogoView()
                .frame(width: 26, height: 26)
            VStack(alignment: .leading, spacing: 0) {
                Text("Hands AI")
                    .font(.system(size: 14, weight: .semibold, design: .rounded))
                Text(backendLabel.text)
                    .font(.system(size: 10, weight: .regular, design: .monospaced))
                    .foregroundStyle(backendLabel.ok ? .green : .secondary)
            }
            Spacer()
            ProfilePicker()
            HStack(spacing: 4) {
                ForEach(AppTab.allCases) { t in
                    TabPill(tab: t, selected: tab == t) { tab = t }
                }
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background(Color.black.opacity(0.15))
    }
}

private struct ProfilePicker: View {
    @EnvironmentObject var profiles: ProfileStore

    var body: some View {
        Menu {
            ForEach(profiles.profiles) { p in
                Button {
                    profiles.select(p)
                } label: {
                    Label {
                        Text(p.name)
                    } icon: {
                        Image(systemName: profiles.selectedID == p.id
                              ? "checkmark.circle.fill" : p.icon)
                    }
                }
            }
        } label: {
            HStack(spacing: 6) {
                Image(systemName: profiles.selected.icon)
                    .font(.system(size: 11, weight: .medium))
                Text(profiles.selected.name)
                    .font(.system(size: 11, weight: .medium))
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(Color.white.opacity(0.08))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .strokeBorder(Color.white.opacity(0.14), lineWidth: 1)
            )
        }
        .menuStyle(.borderlessButton)
        .menuIndicator(.hidden)
        .fixedSize()
        .help("Active profile — changes persona, model, and temperature")
    }
}

private struct TrafficLights: View {
    @State private var hovering = false

    var body: some View {
        HStack(spacing: 6) {
            lightButton(color: Color(red: 1.00, green: 0.36, blue: 0.36), symbol: "xmark") {
                NSApp.terminate(nil)
            }
            .help("Quit Hands AI (⌘Q)")

            lightButton(color: Color(red: 1.00, green: 0.78, blue: 0.27), symbol: "minus") {
                if let delegate = NSApp.delegate as? AppDelegate {
                    delegate.hidePanel()
                }
            }
            .help("Hide panel (⌘W)")
        }
        .onHover { hovering = $0 }
    }

    @ViewBuilder
    private func lightButton(color: Color, symbol: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            ZStack {
                Circle()
                    .fill(color)
                    .overlay(Circle().strokeBorder(.black.opacity(0.20), lineWidth: 0.5))
                if hovering {
                    Image(systemName: symbol)
                        .font(.system(size: 7, weight: .bold))
                        .foregroundStyle(.black.opacity(0.65))
                }
            }
            .frame(width: 12, height: 12)
        }
        .buttonStyle(.plain)
    }
}

private struct TabPill: View {
    let tab: AppTab
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                Image(systemName: tab.symbol)
                    .font(.system(size: 11, weight: .medium))
                Text(tab.rawValue)
                    .font(.system(size: 11, weight: .medium))
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(selected ? Color.white.opacity(0.10) : Color.clear)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .strokeBorder(selected ? Color.white.opacity(0.18) : Color.clear, lineWidth: 1)
            )
            .foregroundStyle(selected ? .primary : .secondary)
        }
        .buttonStyle(.plain)
    }
}

private struct StatusFooter: View {
    @EnvironmentObject var stats: StatsService
    @EnvironmentObject var ollama: OllamaClient
    @EnvironmentObject var claude: ClaudeClient
    @EnvironmentObject var agent: AgentStore

    var body: some View {
        HStack(spacing: 14) {
            Label(String(format: "%.0f%%", stats.stats.cpuPercent), systemImage: "cpu")
            Label(String(format: "%.1f / %.0f GB", stats.stats.ramUsedGB, stats.stats.ramTotalGB),
                  systemImage: "memorychip")
            Spacer()
            Label(agent.activeProvider == "claude" ? claude.selectedModel : ollama.selectedModel,
                  systemImage: agent.activeProvider == "claude" ? "sparkle" : "cube.transparent")
        }
        .font(.system(size: 10, weight: .medium, design: .monospaced))
        .foregroundStyle(.secondary)
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(Color.black.opacity(0.20))
    }
}
