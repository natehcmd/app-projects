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

    private var statusItem: NSStatusItem?
    private var chatWindow: NSWindow?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Silence macOS framework log spam (linkd / nw_* / Process Instance Registry chatter).
        setenv("OS_ACTIVITY_MODE", "disable", 1)

        // Single-instance enforcement: if another Hands AI is already running,
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
        agent.attach(ollama: ollama, claude: claude, claudeCLI: claudeCLI,
                    profiles: profiles, skills: skills)
        remote.attach(agent: agent)
        // A real window on the Mac too, alongside the menu bar icon — it
        // binds to the same AgentStore RemoteServer drives, so it stays in
        // sync with Command Center's Hands AI tab and the iOS app.
        showChatWindow()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }

    // MARK: - Menu bar

    private func setupMainMenu() {
        let main = NSMenu()
        let appMenuItem = NSMenuItem()
        main.addItem(appMenuItem)

        let appMenu = NSMenu()
        appMenuItem.submenu = appMenu

        appMenu.addItem(withTitle: "About Hands AI",
                        action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)),
                        keyEquivalent: "")
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(withTitle: "Show Hands AI",
                        action: #selector(showChatWindow),
                        keyEquivalent: "h").target = self
        appMenu.addItem(withTitle: "Open Command Center",
                        action: #selector(openCommandCenter),
                        keyEquivalent: "o").target = self
        appMenu.addItem(withTitle: "Settings…",
                        action: #selector(openSettings),
                        keyEquivalent: ",").target = self
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(withTitle: "Quit Hands AI",
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
        item.button?.title = "🖐 Hands"

        let menu = NSMenu()
        menu.addItem(withTitle: "Show Hands AI",
                     action: #selector(showChatWindow),
                     keyEquivalent: "h").target = self
        menu.addItem(withTitle: "Open Command Center",
                     action: #selector(openCommandCenter),
                     keyEquivalent: "o").target = self
        menu.addItem(withTitle: "Settings…",
                     action: #selector(openSettings),
                     keyEquivalent: ",").target = self
        menu.addItem(NSMenuItem.separator())
        menu.addItem(withTitle: "Quit Hands AI",
                     action: #selector(NSApplication.terminate(_:)),
                     keyEquivalent: "q")
        // Assigning the menu directly makes AppKit show it on click —
        // no action/performClick dance needed (that pattern used to
        // assign-then-immediately-nil the menu, tearing it down before
        // it could render).
        item.menu = menu
        statusItem = item
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
            let window = NSWindow(
                contentRect: NSRect(x: 0, y: 0, width: 720, height: 580),
                styleMask: [.titled, .closable, .miniaturizable, .resizable],
                backing: .buffered, defer: false)
            window.title = "Hands AI"
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

    @objc private func openSettings() {
        if #available(macOS 14.0, *) {
            NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
        } else {
            NSApp.sendAction(Selector(("showPreferencesWindow:")), to: nil, from: nil)
        }
        NSApp.activate(ignoringOtherApps: true)
    }
}
