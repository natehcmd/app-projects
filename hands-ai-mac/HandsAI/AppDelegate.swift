import AppKit
import SwiftUI

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    let agent = AgentStore()
    let stats = StatsService()
    let ollama = OllamaClient()
    let claude = ClaudeClient()
    let voice = VoiceService()
    let hotkey = HotkeyService()
    let profiles = ProfileStore()
    let skills = SkillsStore()

    private var panel: FloatingPanel?
    private var statusItem: NSStatusItem?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Silence macOS framework log spam (linkd / nw_* / Process Instance Registry chatter).
        setenv("OS_ACTIVITY_MODE", "disable", 1)

        // Single-instance enforcement: if another Hands AI is already running,
        // activate it and quit this copy so we don't end up with 4 panels.
        let me = NSRunningApplication.current
        let bundleID = Bundle.main.bundleIdentifier ?? "com.natehoward.handsai"
        let others = NSRunningApplication.runningApplications(withBundleIdentifier: bundleID)
            .filter { $0 != me }
        if !others.isEmpty {
            others.first?.activate(options: [.activateAllWindows])
            NSApp.terminate(nil)
            return
        }

        NSApp.setActivationPolicy(.regular)
        setupMainMenu()
        setupStatusItem()
        setupPanel()
        registerHotkey()
        stats.start()
        agent.attach(ollama: ollama, claude: claude, voice: voice, profiles: profiles, skills: skills)
        showPanel()
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
        appMenu.addItem(withTitle: "Hide Panel",
                        action: #selector(togglePanel),
                        keyEquivalent: "w").target = self
        appMenu.addItem(withTitle: "Hide Hands AI",
                        action: #selector(NSApplication.hide(_:)),
                        keyEquivalent: "h")
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(withTitle: "Quit Hands AI",
                        action: #selector(NSApplication.terminate(_:)),
                        keyEquivalent: "q")

        let editMenuItem = NSMenuItem()
        main.addItem(editMenuItem)
        let editMenu = NSMenu(title: "Edit")
        editMenuItem.submenu = editMenu
        editMenu.addItem(withTitle: "Cut",       action: #selector(NSText.cut(_:)),       keyEquivalent: "x")
        editMenu.addItem(withTitle: "Copy",      action: #selector(NSText.copy(_:)),      keyEquivalent: "c")
        editMenu.addItem(withTitle: "Paste",     action: #selector(NSText.paste(_:)),     keyEquivalent: "v")
        editMenu.addItem(withTitle: "Select All",action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")

        NSApp.mainMenu = main
    }

    // MARK: - Status bar

    private func setupStatusItem() {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = item.button {
            let menuBarSize: CGFloat = 20
            if let brand = NSImage(named: "BrandLogo") {
                let resized = NSImage(size: NSSize(width: menuBarSize, height: menuBarSize))
                resized.lockFocus()
                NSGraphicsContext.current?.imageInterpolation = .none // crisp pixel art
                brand.draw(in: NSRect(x: 0, y: 0, width: menuBarSize, height: menuBarSize),
                           from: .zero, operation: .sourceOver, fraction: 1.0)
                resized.unlockFocus()
                resized.isTemplate = false // keep full color
                button.image = resized
            } else {
                let fallback = NSImage(systemSymbolName: "hands.sparkles.fill",
                                       accessibilityDescription: "Hands AI")
                fallback?.isTemplate = true
                button.image = fallback
            }
            button.target = self
            button.action = #selector(statusItemClicked(_:))
            button.sendAction(on: [.leftMouseUp, .rightMouseUp])
        }
        statusItem = item
    }

    @objc private func statusItemClicked(_ sender: NSStatusBarButton) {
        let event = NSApp.currentEvent
        if event?.type == .rightMouseUp || event?.modifierFlags.contains(.control) == true {
            showStatusMenu()
        } else {
            togglePanel()
        }
    }

    private func showStatusMenu() {
        let menu = NSMenu()
        let toggleTitle = (panel?.isVisible ?? false) ? "Hide Panel" : "Show Panel"
        menu.addItem(withTitle: toggleTitle,
                     action: #selector(togglePanel),
                     keyEquivalent: "").target = self
        menu.addItem(NSMenuItem.separator())
        menu.addItem(withTitle: "Settings…",
                     action: #selector(openSettings),
                     keyEquivalent: ",").target = self
        menu.addItem(NSMenuItem.separator())
        menu.addItem(withTitle: "Quit Hands AI",
                     action: #selector(NSApplication.terminate(_:)),
                     keyEquivalent: "q")

        statusItem?.menu = menu
        statusItem?.button?.performClick(nil)
        statusItem?.menu = nil
    }

    @objc private func openSettings() {
        if #available(macOS 14.0, *) {
            NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
        } else {
            NSApp.sendAction(Selector(("showPreferencesWindow:")), to: nil, from: nil)
        }
    }

    // MARK: - Panel

    private func setupPanel() {
        let rect = NSRect(x: 0, y: 0, width: 540, height: 700)
        let panel = FloatingPanel(
            contentRect: rect,
            backing: .buffered,
            defer: false
        )
        panel.appDelegate = self

        let root = ContentView()
            .environmentObject(agent)
            .environmentObject(stats)
            .environmentObject(ollama)
            .environmentObject(claude)
            .environmentObject(voice)
            .environmentObject(profiles)
            .environmentObject(skills)

        let hosting = NSHostingView(rootView: root)
        hosting.translatesAutoresizingMaskIntoConstraints = false
        panel.contentView = hosting

        if let cv = panel.contentView {
            NSLayoutConstraint.activate([
                hosting.topAnchor.constraint(equalTo: cv.topAnchor),
                hosting.bottomAnchor.constraint(equalTo: cv.bottomAnchor),
                hosting.leadingAnchor.constraint(equalTo: cv.leadingAnchor),
                hosting.trailingAnchor.constraint(equalTo: cv.trailingAnchor),
            ])
        }

        panel.center()
        self.panel = panel
    }

    @objc func togglePanel() {
        guard let panel else { return }
        if panel.isVisible {
            panel.orderOut(nil)
        } else {
            showPanel()
        }
    }

    func showPanel() {
        guard let panel else { return }
        panel.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func hidePanel() {
        panel?.orderOut(nil)
    }

    // MARK: - Hotkey

    private func registerHotkey() {
        // Option+Space = keyCode 49, modifier optionKey
        hotkey.register(keyCode: 49, modifiers: [.option]) { [weak self] in
            DispatchQueue.main.async { self?.togglePanel() }
        }
    }
}

// MARK: - Floating panel

final class FloatingPanel: NSPanel {
    weak var appDelegate: AppDelegate?

    init(contentRect: NSRect, backing: NSWindow.BackingStoreType, defer flag: Bool) {
        super.init(
            contentRect: contentRect,
            styleMask: [.borderless, .fullSizeContentView, .resizable],
            backing: backing,
            defer: flag
        )
        isFloatingPanel = true
        level = .floating
        collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
        titlebarAppearsTransparent = true
        titleVisibility = .hidden
        isMovableByWindowBackground = true
        backgroundColor = .clear
        isOpaque = false
        hasShadow = true
        hidesOnDeactivate = false
        animationBehavior = .utilityWindow
        minSize = NSSize(width: 480, height: 600)
    }

    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
    override var acceptsFirstResponder: Bool { true }

    override func cancelOperation(_ sender: Any?) {
        appDelegate?.hidePanel()
    }
}
