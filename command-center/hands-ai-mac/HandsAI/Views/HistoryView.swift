import SwiftUI

/// Scrollable past exchanges, grouped by day, persisted across launches.
struct HistoryView: View {
    @EnvironmentObject var history: HistoryStore
    @State private var query: String = ""

    private var filtered: [(day: String, items: [HistoryStore.Exchange])] {
        let q = query.trimmingCharacters(in: .whitespaces).lowercased()
        guard !q.isEmpty else { return history.groupedByDay }
        return history.groupedByDay.compactMap { group in
            let hits = group.items.filter {
                $0.userText.lowercased().contains(q)
                    || $0.assistantText.lowercased().contains(q)
            }
            return hits.isEmpty ? nil : (day: group.day, items: hits)
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            toolbar

            if history.exchanges.isEmpty {
                emptyState
            } else if filtered.isEmpty {
                VStack {
                    Text("Nothing matches \"\(query)\".")
                        .font(.system(size: 12, design: .rounded))
                        .foregroundStyle(.tertiary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 10) {
                        ForEach(filtered, id: \.day) { group in
                            Text(group.day)
                                .font(.system(size: 11, weight: .semibold, design: .rounded))
                                .foregroundStyle(.secondary)
                                .padding(.top, 6)
                            ForEach(group.items) { exchange in
                                ExchangeCard(exchange: exchange)
                            }
                        }
                    }
                    .padding(14)
                }
            }
        }
    }

    private var toolbar: some View {
        HStack(spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: "magnifyingglass")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                TextField("Search history…", text: $query)
                    .textFieldStyle(.plain)
                    .font(.system(size: 12, design: .rounded))
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .glassCard(radius: 8)

            Spacer()

            Text("\(history.exchanges.count) exchange\(history.exchanges.count == 1 ? "" : "s")")
                .font(.system(size: 10, design: .monospaced))
                .foregroundStyle(.tertiary)

            Button(role: .destructive) {
                history.clear()
            } label: {
                Label("Clear", systemImage: "trash")
                    .font(.system(size: 11))
            }
            .controlSize(.small)
            .disabled(history.exchanges.isEmpty)
            .help("Delete all saved history")
        }
        .padding(.horizontal, 14)
        .padding(.top, 10)
        .padding(.bottom, 6)
    }

    private var emptyState: some View {
        VStack(spacing: 8) {
            Image(systemName: "clock.arrow.circlepath")
                .font(.system(size: 24))
                .foregroundStyle(.quaternary)
            Text("No conversations yet.")
                .font(.system(size: 12, design: .rounded))
                .foregroundStyle(.tertiary)
            Text("Every exchange is saved here across launches.")
                .font(.system(size: 11, design: .rounded))
                .foregroundStyle(.quaternary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

private struct ExchangeCard: View {
    @EnvironmentObject var history: HistoryStore
    @EnvironmentObject var voice: VoiceService
    let exchange: HistoryStore.Exchange
    @State private var hovering = false

    private var timeString: String {
        let f = DateFormatter()
        f.timeStyle = .short
        f.dateStyle = .none
        return f.string(from: exchange.timestamp)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(timeString)
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundStyle(.tertiary)
                Image(systemName: exchange.provider == "claude" ? "sparkle" : "cube.transparent")
                    .font(.system(size: 9))
                    .foregroundStyle(.tertiary)
                Spacer()
                if hovering {
                    Button {
                        history.delete(exchange)
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .font(.system(size: 12))
                            .foregroundStyle(.secondary)
                    }
                    .buttonStyle(.plain)
                    .help("Remove this exchange")
                }
            }
            if !exchange.userText.isEmpty {
                Text(exchange.userText)
                    .font(.system(size: 12, weight: .medium, design: .rounded))
                    .textSelection(.enabled)
            }
            if !exchange.assistantText.isEmpty {
                Text(exchange.assistantText)
                    .font(.system(size: 12, design: .rounded))
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
            }
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .glassCard(radius: 12)
        .onHover { hovering = $0 }
        .contextMenu {
            Button("Copy exchange") {
                let text = "You: \(exchange.userText)\n\nHands: \(exchange.assistantText)"
                NSPasteboard.general.clearContents()
                NSPasteboard.general.setString(text, forType: .string)
            }
            Button("Speak reply again") {
                voice.speak(exchange.assistantText)
            }
            .disabled(exchange.assistantText.isEmpty)
            Divider()
            Button("Delete", role: .destructive) { history.delete(exchange) }
        }
    }
}
