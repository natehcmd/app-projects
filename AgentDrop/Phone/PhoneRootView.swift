import SwiftUI

struct PhoneRootView: View {
    @Environment(\.scenePhase) private var phase
    @AppStorage("seenHowTo") private var seenHowTo = false
    @State private var items: [QueueItem] = []
    @State private var showConnect = false
    private let queue = SaveQueue.shared()

    var body: some View {
        NavigationStack {
            List {
                if !seenHowTo {
                    Section {
                        VStack(alignment: .leading, spacing: 8) {
                            Label("How to use", systemImage: "square.and.arrow.up").font(.headline)
                            Text("In Instagram, open a reel, tap Share, then pick AgentDrop. If you don't see it, scroll the app row to the end and tap More.")
                            Text("Your iPhone needs to be on the same Wi-Fi as your Mac (or on Tailscale). Saves made while away wait here and send later.")
                                .foregroundStyle(.secondary)
                            Button("Got it") { seenHowTo = true }.buttonStyle(.borderedProminent)
                        }.padding(.vertical, 4)
                    }
                }
                if !ConnectionStore.isConfigured {
                    Section {
                        Button { showConnect = true } label: {
                            Label("Connect to your Mac", systemImage: "wifi.router")
                        }
                    } footer: { Text("Needed once. Saves are queued until then.") }
                }
                Section("Saved") {
                    if items.isEmpty {
                        Text("Nothing saved yet.").foregroundStyle(.secondary)
                    }
                    ForEach(items) { item in
                        ItemRow(item: item)
                    }
                    .onDelete { idx in
                        for i in idx { queue.delete(items[i].id) }
                        reload()
                    }
                }
            }
            .navigationTitle("AgentDrop")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showConnect = true } label: { Image(systemName: "gearshape") }
                        .accessibilityLabel("Connection settings")
                }
            }
            .refreshable { await retry() }
            .sheet(isPresented: $showConnect, onDismiss: { Task { await retry() } }) { ConnectView() }
        }
        .onAppear { reload(); Task { await retry() } }
        .onChange(of: phase) { _, p in if p == .active { reload(); Task { await retry() } } }
    }

    private func reload() { items = queue.load().sorted { $0.savedAt > $1.savedAt } }
    private func retry() async {
        guard ConnectionStore.isConfigured else { reload(); return }
        await Sender.retryAll(queue: queue)
        reload()
    }
}

struct ItemRow: View {
    let item: QueueItem
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(shortName(item.url)).lineLimit(1).font(.body)
                Spacer()
                badge
            }
            Text(item.savedAt.formatted(date: .abbreviated, time: .shortened))
                .font(.caption).foregroundStyle(.secondary)
            if let e = item.lastError, item.status != .sent {
                Text(e).font(.caption).foregroundStyle(.red)
            }
        }
    }
    private var badge: some View {
        let (text, color): (String, Color) = switch item.status {
        case .sent: ("Sent", .green)
        case .queued: ("Waiting", .orange)
        case .failed: ("Failed", .red)
        }
        return Text(text).font(.caption.bold()).padding(.horizontal, 8).padding(.vertical, 3)
            .background(color.opacity(0.18), in: Capsule()).foregroundStyle(color)
    }
    private func shortName(_ s: String) -> String {
        guard let u = URL(string: s) else { return s }
        return (u.host ?? "").replacingOccurrences(of: "www.", with: "") + u.path
    }
}

struct ConnectView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var address = ConnectionStore.address
    @State private var token = ConnectionStore.token
    @State private var status = ""
    @State private var ok = false
    @State private var testing = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("192.168.1.20:8787", text: $address)
                        .keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                    SecureField("Token", text: $token)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                } header: { Text("Your Mac") } footer: {
                    Text("Address and port of Hammond on your Mac (a Wi-Fi IP, or a Tailscale 100.x.x.x address). The token is in Hammond's Settings, Remote. Your iPhone must be on the same Wi-Fi as the Mac, or on Tailscale.")
                }
                Section {
                    Button {
                        save(); testing = true; status = "Testing..."
                        Task {
                            let r = await Sender.testConnection(address: address, token: token)
                            ok = r.ok; status = r.message; testing = false
                        }
                    } label: { Text(testing ? "Testing..." : "Test connection") }.disabled(testing)
                    if !status.isEmpty {
                        Text(status).foregroundStyle(ok ? .green : .red)
                    }
                }
            }
            .navigationTitle("Connect")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { save(); dismiss() } } }
        }
    }
    private func save() { ConnectionStore.address = address; ConnectionStore.token = token }
}
