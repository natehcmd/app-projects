import SwiftUI

/// Unified OS — the "launcher" that combines Mission Control (web) and
/// Hands AI (native) behind one nate-default shell. Reuses the entire Hands
/// codebase (its @main is excluded); Mission Control loads in a WKWebView.
@main
struct UnifiedApp: App {
    @NSApplicationDelegateAdaptor(UnifiedDelegate.self) var delegate

    var body: some Scene {
        WindowGroup {
            RootShell()
                .environmentObject(delegate.agent)
                .environmentObject(delegate.stats)
                .environmentObject(delegate.ollama)
                .environmentObject(delegate.claude)
                .environmentObject(delegate.voice)
                .environmentObject(delegate.profiles)
                .environmentObject(delegate.skills)
                .environmentObject(delegate.memory)
                .environmentObject(delegate.history)
                .environmentObject(delegate.wake)
                .environmentObject(delegate.briefing)
                .frame(minWidth: 980, minHeight: 680)
        }
        .windowStyle(.hiddenTitleBar)

        Settings {
            SettingsView()
                .environmentObject(delegate.ollama)
                .environmentObject(delegate.claude)
                .environmentObject(delegate.voice)
                .environmentObject(delegate.profiles)
                .environmentObject(delegate.skills)
                .environmentObject(delegate.memory)
                .environmentObject(delegate.wake)
                .environmentObject(delegate.briefing)
        }
    }
}

@MainActor
final class UnifiedDelegate: NSObject, NSApplicationDelegate {
    let agent = AgentStore()
    let stats = StatsService()
    let ollama = OllamaClient()
    let claude = ClaudeClient()
    let voice = VoiceService()
    let hotkey = HotkeyService()
    let profiles = ProfileStore()
    let skills = SkillsStore()
    let memory = MemoryStore()
    let history = HistoryStore()
    let wake = WakeService()
    let briefing = BriefingService()

    func applicationDidFinishLaunching(_ notification: Notification) {
        setenv("OS_ACTIVITY_MODE", "disable", 1)
        NSApp.setActivationPolicy(.regular)
        stats.start()
        agent.attach(ollama: ollama, claude: claude, voice: voice, profiles: profiles,
                     skills: skills, memory: memory, history: history)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }
}
