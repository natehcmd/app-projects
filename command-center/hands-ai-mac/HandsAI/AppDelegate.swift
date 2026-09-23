import AppKit
import SwiftUI

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    let agent = AgentStore()
    let ollama = OllamaClient()
    let claude = ClaudeClient()
    let claudeCLI = ClaudeCLIClient()
    let profiles = ProfileStore()
    let skills = SkillsStore()
    let remote = RemoteServer()
    // Jarvis: hands-free voice on the Mac itself. The chat UI stays in Command
    // Center / iOS; these give the same AgentStore an ears-and-mouth channel.
    let voice = VoiceService()
    let stats = StatsService()
    let memory = MemoryStore()
    let history = HistoryStore()
    let wake = WakeService()
    let briefing = BriefingService()

    private var statusItem: NSStatusItem?
    private var chatWindow: NSWindow?

    /// While true, the mic re-arms automatically after each spoken reply so the
    /// user can hold a back-and-forth conversation without touching anything.
    @AppStorage("voice.handsFree") var handsFree: Bool = true

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Silence macOS framework log spam (linkd / nw_* / Process Instance Registry chatter).
        setenv("OS_ACTIVITY_MODE", "disable", 1)

        // Single-instance enforcement: if another Hammond is already running,
        // activate it and quit this copy.
        let me = NSRunningApplication.current
        let bundleID = Bundle.main.bundleIdentifier ?? "com.natehoward.handsai"
        let others = NSRunningApplication.runningApplications(withBundleIdentifier: bundleID)
            .filter { $0 != me }
        if !others.isEmpty {
            others.first?.activate(options: [.activateAllWindows])
            NSApp.terminate(nil)
            return
        }

        setupMainMenu()
        setupStatusItem()
        stats.start()
        agent.attach(ollama: ollama, claude: claude, claudeCLI: claudeCLI,
                     profiles: profiles, skills: skills,
                     voice: voice, memory: memory, history: history)
        remote.attach(agent: agent)
        briefing.attach(voice: voice, stats: stats)
        setupAmbientVoice()
        // A real window on the Mac too, alongside the menu bar icon — it
        // binds to the same AgentStore RemoteServer drives, so it stays in
        // sync with Command Center's Hammond tab and the iOS app.
        showChatWindow()

        // Warm the briefing in the background so the first "hey jarvis" of the
        // day answers instantly instead of waiting on calendar + weather.
        Task { await briefing.prepare() }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }

    // MARK: - Ambient voice (wake word, clap, hands-free loop)

    /// The AVAudioEngine input node supports exactly one tap, so WakeService and
    /// VoiceService must never listen at once. Every transition below hands the
    /// microphone from one to the other explicitly.
    private func setupAmbientVoice() {
        voice.willStartListening = { [weak self] in self?.wake.suspend() }
        voice.didStopListening = { [weak self] in
            // Only hand the mic back once the reply has been spoken; otherwise
            // the assistant's own voice would trip the wake word.
            guard let self, !self.voice.isSpeaking else { return }
            self.wake.resume()
        }

        wake.onWake = { [weak self] in
            guard let self else { return }
            self.showChatWindow()
            // First wake of the day gets the briefing instead of a bare ack.
            if self.briefing.enabled && !self.briefing.alreadySpokenToday {
                Task { await self.briefing.speakBriefing() }
            } else {
                self.voice.speakAck()
                self.voice.startListening()
            }
        }

        wake.onClap = { [weak self] in
            guard let self else { return }
            self.showChatWindow()
            if self.wake.clapAction == "briefing" {
                Task { await self.briefing.speakBriefing() }
            } else {
                self.voice.speakAck()
                self.voice.startListening()
            }
        }

        voice.onAllSpeechFinished = { [weak self] in
            guard let self, !self.voice.isListening else { return }
            // Hands-free: after the assistant finishes talking, listen again so
            // the user can just reply. Otherwise fall back to wake-word standby.
            if self.handsFree, !self.wake.micMuted, self.agent.state == .idle {
                self.voice.startListening()
            } else {
                self.wake.resume()
            }
        }

        voice.onFinalTranscript = { [weak self] text in
            // Spoken in, so spoken back — typed turns from Command Center or
            // iOS stay silent on the Mac.
            self?.agent.send(text, speakReply: true)
        }

        wake.start()
    }

    // MARK: - Menu bar

    private func setupMainMenu() {
        let main = NSMenu()
        let appMenuItem = NSMenuItem()
        main.addItem(appMenuItem)

        let appMenu = NSMenu()
        appMenuItem.submenu = appMenu

        appMenu.addItem(withTitle: "About Hammond",
                        action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)),
                        keyEquivalent: "")
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(withTitle: "Show Hammond",
                        action: #selector(showChatWindow),
                        keyEquivalent: "h").target = self
        appMenu.addItem(withTitle: "Open Command Center",
                        action: #selector(openCommandCenter),
                        keyEquivalent: "o").target = self
        appMenu.addItem(withTitle: "Settings…",
                        action: #selector(openSettings),
                        keyEquivalent: ",").target = self
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(withTitle: "Quit Hammond",
                        action: #selector(NSApplication.terminate(_:)),
                        keyEquivalent: "q")

        NSApp.mainMenu = main
    }

    // MARK: - Status bar

    private func setupStatusItem() {
        // Plain text title, no rendered image — a custom bitmap-redrawn
        // template image was the likely cause of the icon being invisible
        // for a long stretch of this app's history; plain text is simple
        // and confirmed to actually render in the real menu bar.
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        item.button?.title = "🖐 Hammond"
        // Built on open so the mute check mark and "Start Listening" enablement
        // reflect the current state rather than whatever it was at launch.
        let menu = NSMenu()
        menu.delegate = self
        // Assigning the menu directly makes AppKit show it on click —
        // no action/performClick dance needed (that pattern used to
        // assign-then-immediately-nil the menu, tearing it down before
        // it could render).
        item.menu = menu
        statusItem = item
    }

    fileprivate func rebuildStatusMenu(_ menu: NSMenu) {
        menu.removeAllItems()
        menu.autoenablesItems = false
        menu.addItem(withTitle: "Show Hammond",
                     action: #selector(showChatWindow),
                     keyEquivalent: "h").target = self
        menu.addItem(withTitle: "Open Command Center",
                     action: #selector(openCommandCenter),
                     keyEquivalent: "o").target = self
        menu.addItem(NSMenuItem.separator())

        // Voice quick actions
        let mute = NSMenuItem(title: "Mute Microphone",
                              action: #selector(toggleMicMute),
                              keyEquivalent: "")
        mute.target = self
        mute.state = wake.micMuted ? .on : .off
        menu.addItem(mute)

        let listen = NSMenuItem(title: "Start Listening",
                                action: #selector(startListeningNow),
                                keyEquivalent: "")
        listen.target = self
        listen.isEnabled = !wake.micMuted && !voice.isListening
        menu.addItem(listen)

        menu.addItem(withTitle: "Speak Daily Briefing",
                     action: #selector(speakBriefingNow),
                     keyEquivalent: "").target = self

        menu.addItem(NSMenuItem.separator())
        menu.addItem(withTitle: "Settings…",
                     action: #selector(openSettings),
                     keyEquivalent: ",").target = self
        menu.addItem(NSMenuItem.separator())
        menu.addItem(withTitle: "Quit Hammond",
                     action: #selector(NSApplication.terminate(_:)),
                     keyEquivalent: "q")
    }

    // MARK: - Chat window

    @objc private func showChatWindow() {
        if chatWindow == nil {
            let view = ChatWindowView()
                .environmentObject(agent)
                .environmentObject(ollama)
                .environmentObject(claude)
                .environmentObject(claudeCLI)
                .environmentObject(profiles)
                .environmentObject(skills)
                .environmentObject(voice)
                .environmentObject(stats)
                .environmentObject(memory)
                .environmentObject(history)
                .environmentObject(wake)
                .environmentObject(briefing)
            let window = NSWindow(
                contentRect: NSRect(x: 0, y: 0, width: 720, height: 580),
                styleMask: [.titled, .closable, .miniaturizable, .resizable],
                backing: .buffered, defer: false)
            window.title = "Hammond"
            window.center()
            // Keep the window around when closed rather than deallocating —
            // this is an accessory (menu-bar) app, so re-showing it later
            // needs the same instance, not a freshly-built one.
            window.isReleasedWhenClosed = false
            window.contentView = NSHostingView(rootView: view)
            chatWindow = window
        }
        NSApp.activate(ignoringOtherApps: true)
        chatWindow?.makeKeyAndOrderFront(nil)
    }

    @objc private func openCommandCenter() {
        CommandCenterLauncher.open()
    }

    // MARK: - Voice quick actions

    /// Mute = the app never listens on its own: ambient wake/clap detection
    /// stops and the hands-free loop won't re-arm. Unmuting hands the mic
    /// back to ambient standby.
    @objc private func toggleMicMute() {
        wake.micMuted.toggle()
        if wake.micMuted {
            voice.stopListening()
        }
        // WakeService.reconcile() (via the didSet) handles start/stop of the
        // ambient engine on both edges.
    }

    @objc private func startListeningNow() {
        guard !wake.micMuted else { return }
        showChatWindow()
        voice.startListening()
    }

    @objc private func speakBriefingNow() {
        showChatWindow()
        Task { await briefing.speakBriefing() }
    }

    @objc private func openSettings() {
        if #available(macOS 14.0, *) {
            NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
        } else {
            NSApp.sendAction(Selector(("showPreferencesWindow:")), to: nil, from: nil)
        }
        NSApp.activate(ignoringOtherApps: true)
    }
}

extension AppDelegate: NSMenuDelegate {
    func menuNeedsUpdate(_ menu: NSMenu) {
        rebuildStatusMenu(menu)
    }
}
