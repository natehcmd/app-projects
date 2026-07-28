import SwiftUI

struct MindMapView: View {
    @ObservedObject var store: GraphStore

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 0) {
                if let root = store.nodes[store.rootPath] {
                    MindMapRow(node: root, store: store, depth: 0)
                }
            }
            .padding(.vertical, 8)
            .padding(.horizontal, 4)
        }
        .background(Palette.background)
    }
}

// MARK: - Recursive row

private struct MindMapRow: View {
    let node: GNode
    @ObservedObject var store: GraphStore
    let depth: Int

    private var isSelected: Bool { store.selected?.id == node.id }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // The row itself
            Button {
                withAnimation(.easeInOut(duration: 0.2)) {
                    store.toggle(node)
                }
            } label: {
                rowContent
            }
            .buttonStyle(.plain)

            // Children (expanded directories only)
            if node.item.isDir && node.expanded {
                let childNodes = node.children.compactMap { store.nodes[$0] }
                    .sorted { lhs, rhs in
                        // Directories first, then alphabetical
                        if lhs.item.isDir != rhs.item.isDir { return lhs.item.isDir }
                        return lhs.item.name.localizedStandardCompare(rhs.item.name) == .orderedAscending
                    }
                ForEach(childNodes) { child in
                    MindMapRow(node: child, store: store, depth: depth + 1)
                        .transition(.asymmetric(
                            insertion: .opacity.combined(with: .move(edge: .top)),
                            removal: .opacity
                        ))
                }
            }
        }
    }

    private var rowContent: some View {
        HStack(spacing: 0) {
            // Indentation
            Spacer()
                .frame(width: CGFloat(depth) * 20 + 8)

            // Expand/collapse chevron for directories
            if node.item.isDir {
                Image(systemName: node.expanded ? "chevron.down" : "chevron.right")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundStyle(.secondary)
                    .frame(width: 16, height: 16)
                    .contentTransition(.symbolEffect(.replace))
            } else {
                Spacer().frame(width: 16)
            }

            // Kind-colored dot
            Circle()
                .fill(nodeColor)
                .frame(width: 8, height: 8)
                .padding(.trailing, 6)

            // File/folder icon
            Image(systemName: nodeIcon)
                .font(.system(size: 11))
                .foregroundStyle(nodeColor.opacity(0.8))
                .frame(width: 16)
                .padding(.trailing, 4)

            // Name
            Text(node.item.name)
                .font(.system(size: 12.5, weight: node.item.isDir ? .semibold : .regular))
                .foregroundStyle(node.item.allowed == false ? Palette.blocked : .white)
                .lineLimit(1)

            // Cloud indicator
            if node.item.is_cloud == 1 {
                Text("☁️")
                    .font(.system(size: 10))
                    .padding(.leading, 4)
            }

            // Lock indicator
            if node.item.allowed == false {
                Image(systemName: "lock.fill")
                    .font(.system(size: 8))
                    .foregroundStyle(Palette.blocked)
                    .padding(.leading, 4)
            }

            Spacer()

            // Metadata: child count for dirs, file size for files
            if node.item.isDir {
                if let count = node.item.child_count, count > 0 {
                    Text("\(count)")
                        .font(.system(size: 10).monospacedDigit())
                        .foregroundStyle(.secondary)
                        .padding(.trailing, 4)
                    Image(systemName: "doc.on.doc")
                        .font(.system(size: 9))
                        .foregroundStyle(.secondary)
                }
            } else {
                if let size = node.item.size, size > 0 {
                    Text(ByteCountFormatter.string(fromByteCount: Int64(size), countStyle: .file))
                        .font(.system(size: 10).monospacedDigit())
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding(.vertical, 5)
        .padding(.horizontal, 8)
        .background(
            RoundedRectangle(cornerRadius: 5)
                .fill(isSelected ? Color.white.opacity(0.1) : Color.clear)
        )
        .contentShape(Rectangle())
    }

    private var nodeColor: Color {
        node.item.allowed == false ? Palette.blocked : Palette.color(for: node.item.kind)
    }

    private var nodeIcon: String {
        if node.item.isDir {
            return node.expanded ? "folder.fill" : "folder"
        }
        switch node.item.kind {
        case "code":    return "chevron.left.forwardslash.chevron.right"
        case "doc":     return "doc.text"
        case "data":    return "tablecells"
        case "image":   return "photo"
        case "video":   return "film"
        case "audio":   return "waveform"
        case "archive": return "archivebox"
        default:        return "doc"
        }
    }
}
