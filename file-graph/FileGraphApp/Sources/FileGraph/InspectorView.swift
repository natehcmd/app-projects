import SwiftUI

struct InspectorView: View {
    @ObservedObject var store: GraphStore

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                if let node = store.selected {
                    fileSection(node)
                    Divider()
                }
                privacySection
            }
            .padding(14)
        }
        .frame(width: 300)
        .background(.ultraThinMaterial)
    }

    @ViewBuilder
    private func fileSection(_ node: GNode) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 8) {
                Circle().fill(Palette.color(for: node.item.kind)).frame(width: 10, height: 10)
                Text(node.item.name).font(.system(size: 14, weight: .semibold))
                    .lineLimit(2)
            }
            Text(node.id).font(.system(size: 11)).foregroundStyle(.secondary)
                .lineLimit(3).textSelection(.enabled)
            HStack(spacing: 10) {
                Text(node.item.kind)
                if let size = node.item.size, size > 0, !node.item.isDir {
                    Text(ByteCountFormatter.string(fromByteCount: Int64(size), countStyle: .file))
                }
                if node.item.is_cloud == 1 { Text("☁️ metadata only") }
            }
            .font(.system(size: 11)).foregroundStyle(.secondary)

            if node.item.allowed == false {
                Label("Hidden from AIs", systemImage: "lock.fill")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(Palette.blocked)
            }
            if node.item.isDir {
                Button(node.item.allowed == false ? "Allow AI access" : "Block AI access") {
                    store.setRule(prefix: node.id, allow: node.item.allowed == false)
                    store.selected?.item.allowed = node.item.allowed == false
                }
                .controlSize(.small)
            }
            HStack {
                Button("Reveal in Finder") {
                    NSWorkspace.shared.activateFileViewerSelecting(
                        [URL(fileURLWithPath: node.id)])
                }
                .controlSize(.small)
            }
        }

        if let related = store.related {
            if let semantic = related.semantic, !semantic.isEmpty {
                sectionHeader("Similar files")
                ForEach(semantic.prefix(8)) { item in resultRow(item) }
            }
            if let siblings = related.siblings, !siblings.isEmpty {
                sectionHeader("Same folder")
                ForEach(siblings.prefix(6)) { item in resultRow(item) }
            }
        } else if !node.item.isDir {
            ProgressView().controlSize(.small)
        }
    }

    private var privacySection: some View {
        VStack(alignment: .leading, spacing: 8) {
            sectionHeader("AI Access Control")
            Text("What Claude & other AIs can see. Longest matching path wins. Everything stays on this Mac.")
                .font(.system(size: 11)).foregroundStyle(.secondary)
            ForEach(store.rules) { rule in
                HStack(spacing: 8) {
                    Toggle("", isOn: Binding(
                        get: { rule.allow == 1 },
                        set: { store.setRule(prefix: rule.prefix, allow: $0) }))
                        .toggleStyle(.switch).controlSize(.mini).labelsHidden()
                    Text(rule.prefix.replacingOccurrences(
                        of: NSHomeDirectory(), with: "~"))
                        .font(.system(size: 11)).lineLimit(2)
                    Spacer()
                    Button { store.deleteRule(rule.id) } label: {
                        Image(systemName: "xmark").font(.system(size: 9))
                    }
                    .buttonStyle(.plain).foregroundStyle(.secondary)
                }
            }
            if store.rules.isEmpty {
                Text("No rules — everything indexed is visible to AIs.")
                    .font(.system(size: 11)).foregroundStyle(.secondary)
            }
        }
    }

    private func sectionHeader(_ title: String) -> some View {
        Text(title.uppercased())
            .font(.system(size: 10, weight: .semibold))
            .foregroundStyle(.secondary)
            .padding(.top, 4)
    }

    private func resultRow(_ item: FileItem) -> some View {
        Button {
            Task { await store.reveal(item.path) }
        } label: {
            HStack(spacing: 6) {
                Circle().fill(Palette.color(for: item.kind)).frame(width: 7, height: 7)
                Text(item.name).font(.system(size: 11.5)).lineLimit(1)
                Spacer()
                if let score = item.score {
                    Text("\(Int(score * 100))%")
                        .font(.system(size: 10)).foregroundStyle(.secondary)
                }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}
