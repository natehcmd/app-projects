import SwiftUI

struct ReelDetailView: View {
    let item: QueueItem
    @State private var detail: ReelDetail?
    @State private var notFound = false
    @State private var error: String?
    @State private var messages: [ChatMessage] = []
    @State private var draft = ""
    @State private var sending = false
    @State private var polls = 0
    private let store = ChatStore.shared()
    private var reelID: String? { ReelID.from(url: item.url) }

    var body: some View {
        Group {
            if let id = reelID { content(id) }
            else {
                ContentUnavailableView("Details are Instagram-only for now",
                                       systemImage: "info.circle",
                                       description: Text("TikTok and YouTube saves still go to your Mac, but they don't have a description or chat yet."))
            }
        }
        .navigationTitle(detail?.title?.isEmpty == false ? detail!.title! : "Reel")
        .navigationBarTitleDisplayMode(.inline)
    }

    @ViewBuilder private func content(_ id: String) -> some View {
        List {
            statusSection
            if let d = detail {
                if let bullets = d.description, !bullets.isEmpty {
                    Section {
                        ForEach(bullets, id: \.self) { Text("• " + $0) }
                    } header: { Text("What it's about") } footer: {
                        if let c = d.checked, !c.isEmpty { Text("Description: \(c)") }
                    }
                }
                Section("Links") {
                    if (d.links ?? []).isEmpty {
                        Text(d.status == "ready" ? "No links found for this reel." : "Looking for links...")
                            .foregroundStyle(.secondary)
                    }
                    ForEach(d.links ?? []) { link in LinkRow(link: link) }
                }
            }
            Section {
                ForEach(messages) { m in Bubble(msg: m) }
                if sending { HStack { ProgressView(); Text("Thinking on your Mac...").foregroundStyle(.secondary) } }
                if messages.isEmpty && !sending {
                    Text("Ask anything about this reel. Answers come only from what the reel says.")
                        .foregroundStyle(.secondary)
                }
            } header: { Text("Chat") }
        }
        .refreshable { await load(id) }
        .task(id: id) {
            messages = store.load(id)
            await load(id)
            // Auto-refresh every few seconds while the Mac is still working.
            while !Task.isCancelled, shouldPoll {
                try? await Task.sleep(nanoseconds: 4_000_000_000)
                if Task.isCancelled { break }
                polls += 1
                await load(id)
            }
        }
        .safeAreaInset(edge: .bottom) { inputBar(id) }
    }

    private var shouldPoll: Bool {
        if notFound { return polls < 40 }                  // ~3 minutes for the Mac to pick it up
        return detail?.status == "processing" && polls < 200
    }

    @ViewBuilder private var statusSection: some View {
        if let e = error {
            Section { Label(e, systemImage: "wifi.exclamationmark").foregroundStyle(.red) }
        } else if notFound {
            Section { HStack { ProgressView(); Text("Waiting for your Mac to pick this up...") } }
        } else if detail == nil {
            Section { HStack { ProgressView(); Text("Loading...") } }
        } else if detail?.status == "processing" {
            Section { HStack { ProgressView(); Text("Processing on your Mac...") } }
        } else if detail?.status == "error" {
            Section { Label("Your Mac couldn't describe this one. Pull down to retry.", systemImage: "exclamationmark.triangle").foregroundStyle(.orange) }
        }
    }

    private func inputBar(_ id: String) -> some View {
        HStack(spacing: 8) {
            TextField("Ask about this reel", text: $draft, axis: .vertical)
                .lineLimit(1...4).textFieldStyle(.roundedBorder)
                .submitLabel(.send).onSubmit { Task { await send(id) } }
            Button { Task { await send(id) } } label: { Image(systemName: "arrow.up.circle.fill").font(.title2) }
                .disabled(sending || draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                .accessibilityLabel("Send")
        }
        .padding(.horizontal).padding(.vertical, 8).background(.bar)
    }

    private func load(_ id: String) async {
        switch await Sender.fetchDetail(id: id) {
        case .detail(let d): detail = d; notFound = false; error = nil
        case .notFound: notFound = true; error = nil
        case .failed(let m): error = m
        }
    }

    private func send(_ id: String) async {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !sending else { return }
        let history = store.history(id)        // before this message
        let mine = ChatMessage(role: "user", text: text)
        store.append(id, mine); messages.append(mine); draft = ""; sending = true
        switch await Sender.chat(id: id, message: text, history: history) {
        case .answer(let a, let checked):
            let m = ChatMessage(role: "assistant", text: a, checked: checked)
            store.append(id, m); messages.append(m)
        case .failed(let e):
            messages.append(ChatMessage(role: "assistant", text: "Couldn't get an answer: \(e)"))  // not saved
        }
        sending = false
    }
}

private struct LinkRow: View {
    let link: ReelLink
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                if let u = URL(string: link.url), ["http", "https"].contains(u.scheme?.lowercased()) {
                    Link(link.title?.isEmpty == false ? link.title! : link.url, destination: u).lineLimit(2)
                } else { Text(link.url) }
                Spacer()
                let ok = link.checked == "verified"
                Text(ok ? "verified" : "unsure").font(.caption2.bold())
                    .padding(.horizontal, 7).padding(.vertical, 2)
                    .background((ok ? Color.green : Color.orange).opacity(0.18), in: Capsule())
                    .foregroundStyle(ok ? .green : .orange)
            }
            Text(link.url).font(.caption2).foregroundStyle(.secondary).lineLimit(1)
            ForEach(link.summary ?? [], id: \.self) { Text("• " + $0).font(.caption).foregroundStyle(.secondary) }
        }
    }
}

private struct Bubble: View {
    let msg: ChatMessage
    var body: some View {
        let mine = msg.role == "user"
        VStack(alignment: mine ? .trailing : .leading, spacing: 2) {
            Text(msg.text).padding(10)
                .background(mine ? Color.accentColor : Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 14))
                .foregroundStyle(mine ? Color.white : Color.primary)
            if !mine, let c = msg.checked { Text(c).font(.caption2).foregroundStyle(.secondary) }
        }
        .frame(maxWidth: .infinity, alignment: mine ? .trailing : .leading)
        .listRowSeparator(.hidden)
    }
}
