import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var ollama: OllamaClient
    @EnvironmentObject var claude: ClaudeClient
    @EnvironmentObject var claudeCLI: ClaudeCLIClient
    @EnvironmentObject var profiles: ProfileStore
    @EnvironmentObject var skills: SkillsStore
    @EnvironmentObject var remote: RemoteServer
    @EnvironmentObject var voice: VoiceService
    @EnvironmentObject var memory: MemoryStore
    @EnvironmentObject var wake: WakeService
    @EnvironmentObject var briefing: BriefingService
    @AppStorage("chat.provider") private var provider: String = "ollama"
    @AppStorage("voice.handsFree") private var handsFree: Bool = true
    @State private var ollamaURLField: String = ""
    @State private var ollamaURLInvalid = false

    private func applyOllamaURL() {
        ollamaURLInvalid = !ollama.setBaseURL(ollamaURLField)
        if !ollamaURLInvalid { ollamaURLField = ollama.baseURL.absoluteString }
    }

    var body: some View {
        TabView {
            backendTab
                .tabItem { Label("Backend", systemImage: "brain") }
            ProfilesTab()
                .tabItem { Label("Profiles", systemImage: "person.2") }
            SkillsTab()
                .tabItem { Label("Skills", systemImage: "book.closed") }
            remoteTab
                .tabItem { Label("Remote", systemImage: "iphone") }
            voiceTab
                .tabItem { Label("Voice", systemImage: "waveform") }
            wakeTab
                .tabItem { Label("Wake", systemImage: "ear") }
            MemoryTab()
                .tabItem { Label("Memory", systemImage: "brain.head.profile") }
            aboutTab
                .tabItem { Label("About", systemImage: "info.circle") }
        }
        .frame(width: 560, height: 480)
    }

    private var remoteTab: some View {
        Form {
            Section("iPhone remote control") {
                Toggle("Let the Hammond Remote app connect", isOn: $remote.enabled)
                HStack {
                    Circle()
                        .fill(remote.isRunning ? .green : .secondary.opacity(0.4))
                        .frame(width: 8, height: 8)
                    Text(remote.isRunning ? "Listening on port \(remote.port)" : "Not running")
                        .foregroundStyle(.secondary)
                }
                if let error = remote.lastError {
                    Label(error, systemImage: "exclamationmark.triangle.fill")
                        .font(.system(size: 11))
                        .foregroundStyle(.red)
                }
            }
            Section("Connection details for the phone") {
                LabeledContent("Port", value: "\(remote.port)")
                HStack {
                    Text(remote.token)
                        .font(.system(size: 11, design: .monospaced))
                        .textSelection(.enabled)
                    Spacer()
                    Button("Copy") {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(remote.token, forType: .string)
                    }
                    .controlSize(.small)
                    Button("New token") {
                        remote.token = RemoteServer.generateToken()
                    }
                    .controlSize(.small)
                }
                Text("On the phone: enter this Mac's Tailscale IP (check the Tailscale menu-bar icon, or run `tailscale ip -4` in Terminal), this port, and this token.")
                    .font(.system(size: 10))
                    .foregroundStyle(.tertiary)
                if remote.isRunning {
                    Text("Already running — a new token only takes effect after you toggle this off and back on.")
                        .font(.system(size: 10))
                        .foregroundStyle(.orange)
                }
            }
            Section {
                Text("Off by default — only turns on when you flip the toggle above, same as everything else in this app that reaches outside it.")
                    .font(.system(size: 10))
                    .foregroundStyle(.tertiary)
            }
        }
        .formStyle(.grouped)
    }

    /// Wake word, double clap, hands-free conversation, and the daily briefing.
    private var wakeTab: some View {
        Form {
            Section("Wake word") {
                Toggle("Listen for a wake phrase", isOn: $wake.wakeEnabled)
                TextField("Phrase", text: $wake.wakePhrase)
                    .disabled(!wake.wakeEnabled)
                Text("Say it any time to bring Hammond up and start talking. "
                     + "Recognition runs on-device — nothing leaves the Mac while idle.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Section("Double clap") {
                Toggle("Trigger on a double clap", isOn: $wake.clapEnabled)
                Picker("A double clap", selection: $wake.clapAction) {
                    Text("Starts listening").tag("listen")
                    Text("Speaks the briefing").tag("briefing")
                }
                .disabled(!wake.clapEnabled)
                Text("Two sharp claps within about a second. Handy from across the room.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Section("Conversation") {
                Toggle("Hands-free follow-ups", isOn: $handsFree)
                Text("After Hammond finishes speaking, the microphone re-arms so "
                     + "you can simply reply — no tapping, no wake phrase.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Section("Daily briefing") {
                Toggle("Speak a briefing on the first wake of the day", isOn: $briefing.enabled)
                HStack {
                    Button("Preview now") {
                        Task { await briefing.speakBriefing() }
                    }
                    Button("Rebuild") { briefing.invalidate() }
                        .help("Discard the cached briefing and gather fresh data")
                }
                Text("Your calendar, reminders, weather, and machine health — "
                     + "prepared in the background so it answers instantly.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Section("Microphone") {
                Toggle("Mute microphone", isOn: $wake.micMuted)
                Text("While muted, Hammond never listens on its own — no wake word, "
                     + "no claps, no hands-free re-arm. Also in the menu-bar right-click menu.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Section {
                Label(wake.micMuted ? "Microphone muted"
                      : wake.isAmbient ? "Listening for triggers" : "Ambient detection off",
                      systemImage: wake.isAmbient ? "waveform.badge.mic" : "mic.slash")
                    .foregroundStyle(wake.micMuted ? .orange : wake.isAmbient ? .green : .secondary)
                    .font(.callout)
            }
        }
        .formStyle(.grouped)
        .padding()
    }

    private var voiceTab: some View {
        Form {
            Section("Voice output") {
                Toggle("Speak replies", isOn: $voice.voiceEnabled)
                Picker("Voice", selection: $voice.selectedVoiceID) {
                    ForEach(voice.availableVoices, id: \.identifier) { v in
                        Text("\(v.name) — \(v.language) · \(v.quality.label)").tag(v.identifier)
                    }
                }
                HStack {
                    Spacer()
                    Button("Test voice") {
                        voice.speak("Good evening, sir. All systems nominal.")
                    }
                }
            }
            if voice.hasOnlyDefaultVoices {
                Section {
                    Label {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("For a proper Jarvis voice, install a premium British voice.")
                                .font(.system(size: 12))
                            Text("System Settings → Accessibility → Spoken Content → System Voice → Manage Voices → English (UK) → tick \"Daniel (Premium)\".")
                                .font(.system(size: 11))
                                .foregroundStyle(.secondary)
                            Button("Open System Settings") {
                                if let url = URL(string: "x-apple.systempreferences:com.apple.preference.universalaccess?Spoken_Content") {
                                    NSWorkspace.shared.open(url)
                                }
                            }
                            .controlSize(.small)
                            .padding(.top, 4)
                        }
                    } icon: {
                        Image(systemName: "info.circle.fill")
                            .foregroundStyle(.yellow)
                    }
                }
            }
        }
        .formStyle(.grouped)
    }

    private var backendTab: some View {
        Form {
            Section("Provider") {
                Picker("Chat provider", selection: $provider) {
                    Text("Ollama (local, private)").tag("ollama")
                    Text("Claude (Anthropic API)").tag("claude")
                    Text("Claude Code (CLI)").tag("claude-cli")
                }
                .pickerStyle(.menu)
                if provider == "claude" && !claude.isConfigured {
                    Label(claudeCLI.isConfigured
                          ? "No API key set — using Claude Code (CLI) below instead."
                          : "No API key set and Claude Code (CLI) isn't available either — Hammond stays on Ollama.",
                          systemImage: "info.circle.fill")
                        .font(.system(size: 11))
                        .foregroundStyle(.yellow)
                }
                if provider == "claude-cli" && !claudeCLI.isConfigured {
                    Label(claudeCLI.resolveError ?? "claude CLI not found — until then, Hammond stays on Ollama.",
                          systemImage: "exclamationmark.triangle.fill")
                        .font(.system(size: 11))
                        .foregroundStyle(.yellow)
                }
            }
            Section("Claude") {
                SecureField("API key (sk-ant-…)", text: $claude.apiKey)
                    .textFieldStyle(.roundedBorder)
                    .font(.system(size: 11, design: .monospaced))
                Picker("Model", selection: $claude.selectedModel) {
                    ForEach(ClaudeClient.models, id: \.id) { m in
                        Text(m.label).tag(m.id)
                    }
                }
                Text("Key is stored locally in app preferences and sent only to api.anthropic.com. Optional — without one, \"Claude\" answers through Claude Code (CLI) below instead.")
                    .font(.system(size: 10))
                    .foregroundStyle(.tertiary)
            }
            Section("Claude Code (CLI)") {
                HStack {
                    Circle()
                        .fill(claudeCLI.isConfigured ? .green : .red)
                        .frame(width: 8, height: 8)
                    Text(claudeCLI.resolvedPath ?? claudeCLI.resolveError ?? "Looking for claude…")
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
                Picker("Model", selection: $claudeCLI.selectedModel) {
                    ForEach(ClaudeCLIClient.models, id: \.id) { m in
                        Text(m.label).tag(m.id)
                    }
                }
                Toggle("Let it run any command without asking", isOn: $claudeCLI.skipPermissions)
                if claudeCLI.skipPermissions {
                    Label("Full autonomy — no confirmation of any kind, including destructive commands. Only enable if you understand the risk.",
                          systemImage: "exclamationmark.triangle.fill")
                        .font(.system(size: 10))
                        .foregroundStyle(.red)
                } else {
                    Text("Default: read-only tools + web only (Read, Grep, Glob, WebFetch, WebSearch, and a few safe read-only Bash commands). Anything else is denied, not prompted — there's no terminal here to approve it in.")
                        .font(.system(size: 10))
                        .foregroundStyle(.tertiary)
                }
                Button("New session") { claudeCLI.resetSession() }
                    .controlSize(.small)
                    .help("Forget the current conversation context and start fresh next message.")
            }
            Section("Ollama") {
                HStack {
                    Circle()
                        .fill(ollama.isReachable ? .green : .red)
                        .frame(width: 8, height: 8)
                    Text(ollama.isReachable ? "Ollama reachable" : "Ollama not running")
                        .foregroundStyle(.secondary)
                    Spacer()
                    Button("Refresh") { Task { await ollama.refresh() } }
                }
                HStack {
                    TextField("Server URL", text: $ollamaURLField)
                        .textFieldStyle(.roundedBorder)
                        .font(.system(size: 11, design: .monospaced))
                        .onSubmit(applyOllamaURL)
                    Button("Apply", action: applyOllamaURL)
                        .disabled(ollamaURLField.trimmingCharacters(in: .whitespaces)
                                  == ollama.baseURL.absoluteString)
                }
                if ollamaURLInvalid {
                    Text("That doesn't look like a valid http(s) URL — leave it empty to restore \(OllamaClient.defaultBaseURL.absoluteString).")
                        .font(.system(size: 10))
                        .foregroundStyle(.red)
                } else {
                    Text("Point this at another machine to use a remote Ollama, e.g. http://192.168.1.50:11434. Empty restores the default.")
                        .font(.system(size: 10))
                        .foregroundStyle(.tertiary)
                }
            }
            Section("Ollama model") {
                Picker("Active model", selection: $ollama.selectedModel) {
                    ForEach(ollama.availableModels) { m in
                        Text("\(m.name) · \(String(format: "%.1f", m.sizeGB)) GB").tag(m.name)
                    }
                }
                .pickerStyle(.menu)
                .onChange(of: ollama.selectedModel) { _ in
                    ollama.userExplicitlySelectedModel = true
                }
                if !ollama.isReachable {
                    Text("Start Ollama with: `ollama serve` in a terminal.")
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(.secondary)
                }
            }
        }
        .formStyle(.grouped)
        .onAppear { ollamaURLField = ollama.baseURL.absoluteString }
    }

    // MARK: - Profiles

    private struct ProfilesTab: View {
        @EnvironmentObject var profiles: ProfileStore
        @EnvironmentObject var ollama: OllamaClient
        @State private var editingID: UUID?

        var body: some View {
            HSplitView {
                List(selection: $editingID) {
                    ForEach(profiles.profiles) { p in
                        HStack(spacing: 8) {
                            Image(systemName: p.icon)
                                .frame(width: 18)
                            VStack(alignment: .leading, spacing: 1) {
                                HStack(spacing: 6) {
                                    Text(p.name).font(.system(size: 12, weight: .medium))
                                    if profiles.selectedID == p.id {
                                        Text("active")
                                            .font(.system(size: 9, weight: .semibold))
                                            .padding(.horizontal, 5).padding(.vertical, 1)
                                            .background(Capsule().fill(Color.green.opacity(0.25)))
                                    }
                                }
                                Text(p.tagline)
                                    .font(.system(size: 10))
                                    .foregroundStyle(.secondary)
                                    .lineLimit(1)
                            }
                        }
                        .tag(p.id)
                    }
                }
                .frame(minWidth: 190)
                .safeAreaInset(edge: .bottom) {
                    HStack {
                        Button {
                            editingID = profiles.addProfile().id
                        } label: { Image(systemName: "plus") }
                        Button {
                            if let id = editingID,
                               let p = profiles.profiles.first(where: { $0.id == id }) {
                                profiles.delete(p)
                                editingID = nil
                            }
                        } label: { Image(systemName: "minus") }
                        .disabled(editingID == nil ||
                                  profiles.profiles.first(where: { $0.id == editingID })?.builtIn == true)
                        Spacer()
                        Button("Reset built-ins") { profiles.resetBuiltIns() }
                            .controlSize(.small)
                    }
                    .padding(8)
                }

                if let id = editingID ?? profiles.selectedID,
                   let idx = profiles.profiles.firstIndex(where: { $0.id == id }) {
                    ProfileEditor(profile: bindingFor(idx))
                        .frame(minWidth: 280)
                } else {
                    Text("Select a profile").foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
        }

        private func bindingFor(_ idx: Int) -> Binding<Profile> {
            Binding(
                get: { profiles.profiles[idx] },
                set: { profiles.update($0) }
            )
        }
    }

    private struct ProfileEditor: View {
        @Binding var profile: Profile
        @EnvironmentObject var ollama: OllamaClient
        @EnvironmentObject var profiles: ProfileStore

        var body: some View {
            Form {
                Section {
                    TextField("Name", text: $profile.name)
                        .disabled(profile.builtIn)
                    TextField("Tagline", text: $profile.tagline)
                    Picker("Model", selection: $profile.model) {
                        Text("Auto (global)").tag("")
                        ForEach(ollama.availableModels) { m in
                            Text(m.name).tag(m.name)
                        }
                    }
                    HStack {
                        Text("Temperature")
                        Slider(value: $profile.temperature, in: 0...1)
                        Text(String(format: "%.1f", profile.temperature))
                            .font(.system(size: 11, design: .monospaced))
                            .frame(width: 28)
                    }
                }
                Section("Persona (injected into the system prompt)") {
                    TextEditor(text: $profile.persona)
                        .font(.system(size: 11))
                        .frame(minHeight: 120)
                }
                Section {
                    HStack {
                        Spacer()
                        Button("Use this profile") { profiles.select(profile) }
                            .disabled(profiles.selectedID == profile.id)
                    }
                }
            }
            .formStyle(.grouped)
        }
    }

    // MARK: - Skills

    /// What Hammond has remembered, grouped by tier, with delete.
    private struct MemoryTab: View {
        @EnvironmentObject var memory: MemoryStore
        @State private var newText = ""
        @State private var newTier = "user"

        private let tiers: [(id: String, label: String, symbol: String)] = [
            ("user", "About you", "person"),
            ("work", "Your work", "hammer"),
            ("policy", "Standing rules", "checklist"),
        ]

        var body: some View {
            VStack(alignment: .leading, spacing: 10) {
                if memory.entries.isEmpty {
                    Spacer()
                    VStack(spacing: 6) {
                        Image(systemName: "brain.head.profile")
                            .font(.system(size: 34))
                            .foregroundStyle(.secondary)
                        Text("Nothing remembered yet.")
                            .foregroundStyle(.secondary)
                        Text("Tell Hammond something about yourself — it saves it on its own.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity)
                    Spacer()
                } else {
                    List {
                        ForEach(tiers, id: \.id) { tier in
                            let items = memory.entries.filter { $0.tier == tier.id }
                            if !items.isEmpty {
                                Section {
                                    ForEach(items) { entry in
                                        HStack {
                                            Text(entry.text)
                                                .font(.callout)
                                            Spacer()
                                            Button {
                                                _ = memory.forget(query: entry.text)
                                            } label: {
                                                Image(systemName: "xmark.circle.fill")
                                                    .foregroundStyle(.secondary)
                                            }
                                            .buttonStyle(.plain)
                                            .help("Forget this")
                                        }
                                    }
                                } header: {
                                    Label(tier.label, systemImage: tier.symbol)
                                }
                            }
                        }
                    }
                }

                HStack(spacing: 8) {
                    Picker("", selection: $newTier) {
                        ForEach(tiers, id: \.id) { Text($0.label).tag($0.id) }
                    }
                    .frame(width: 140)
                    TextField("Teach it something…", text: $newText)
                        .textFieldStyle(.roundedBorder)
                        .onSubmit(add)
                    Button("Add", action: add)
                        .disabled(newText.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
            .padding()
        }

        private func add() {
            let text = newText.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !text.isEmpty else { return }
            _ = memory.remember(tier: newTier, text: text)
            newText = ""
        }
    }

    private struct SkillsTab: View {
        @EnvironmentObject var skills: SkillsStore

        var body: some View {
            Form {
                Section {
                    HStack {
                        Text("\(skills.skills.count) skills in ~/hands-ai-skills")
                            .foregroundStyle(.secondary)
                        Spacer()
                        Button("Open Folder") {
                            NSWorkspace.shared.open(URL(fileURLWithPath: SkillsStore.directory))
                        }
                        Button("Reload") { skills.reload() }
                    }
                }
                Section("Installed skills") {
                    if skills.skills.isEmpty {
                        Text("No skills yet. Drop markdown files into the folder — first line `# Name`, second `> description`, then the steps.")
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                    }
                    ForEach(skills.skills) { s in
                        VStack(alignment: .leading, spacing: 2) {
                            HStack {
                                Text(s.name).font(.system(size: 12, weight: .medium))
                                Spacer()
                                Text(s.slug)
                                    .font(.system(size: 10, design: .monospaced))
                                    .foregroundStyle(.tertiary)
                            }
                            Text(s.description.isEmpty ? "(no description)" : s.description)
                                .font(.system(size: 11))
                                .foregroundStyle(.secondary)
                        }
                        .padding(.vertical, 2)
                    }
                }
                Section {
                    Text("Ask Hammond to \"use the daily briefing skill\" — or just ask for a briefing; it loads matching skills on its own via the use_skill tool.")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }
            }
            .formStyle(.grouped)
        }
    }

    private var aboutTab: some View {
        VStack(spacing: 14) {
            LogoView().frame(width: 110, height: 110)
            Text("Hammond")
                .font(.system(size: 18, weight: .semibold, design: .rounded))
            Text("Local-first agent engine for macOS")
                .font(.system(size: 12, design: .rounded))
                .foregroundStyle(.secondary)
            Text("v0.7.0 — headless · 41 tools · Command Center + iOS remote · Jarvis voice, wake word, memory, briefing")
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(.tertiary)
            Spacer()
        }
        .padding(.top, 24)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
