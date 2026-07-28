import Foundation
import simd
import SwiftUI

final class GNode: Identifiable {
    let id: String            // path
    var item: FileItem
    var position: SIMD3<Float>
    var velocity = SIMD3<Float>(0, 0, 0)
    var expanded = false
    var children: [String] = []
    let parent: String?
    var pinned = false

    var radius: Float {
        item.isDir ? min(18, 8 + 1.8 * log2(Float(1 + (item.child_count ?? 0)))) : 5
    }

    init(item: FileItem, parent: String?, near: SIMD3<Float>) {
        self.id = item.path
        self.item = item
        self.parent = parent
        let a = Float.random(in: 0...(2 * .pi))
        let b = Float.random(in: -0.6...0.6)
        position = near + SIMD3(cos(a) * 70, sin(a) * 70, sin(b) * 40)
    }
}

enum GraphMode: String, CaseIterable { case twoD = "2D", threeD = "3D", mindMap = "Mind Map" }

@MainActor
final class GraphStore: ObservableObject {
    @Published var tick = 0                    // drives canvas redraw
    @Published var mode: GraphMode = .twoD
    @Published var selected: GNode?
    @Published var searchResults: [FileItem] = []
    @Published var rules: [AccessRule] = []
    @Published var statusText = "connecting…"
    @Published var related: RelatedResponse?
    @Published var reduceMotion = NSWorkspace.shared.accessibilityDisplayShouldReduceMotion

    var nodes: [String: GNode] = [:]
    var edges: [(String, String)] = []
    var rootPath = ""
    let maxNodes = 1200

    private var timer: Timer?

    func start() async {
        statusText = "starting backend…"
        await Backend.ensureRunning()
        await loadRoot()
        await refreshRules()
        await refreshStats()
        let interval = 1.0 / 30.0
        timer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.step() }
        }
    }

    func loadRoot() async {
        guard let tree: TreeResponse = try? await Backend.get("api/tree") else {
            statusText = "backend unreachable"; return
        }
        rootPath = tree.path
        nodes.removeAll(); edges.removeAll()
        let rootItem = FileItem(path: tree.path, name: "Home", kind: "folder",
                                is_dir: 1, child_count: tree.children.count)
        let root = GNode(item: rootItem, parent: nil, near: .zero)
        root.position = .zero
        root.pinned = true
        root.expanded = true
        nodes[root.id] = root
        addChildren(tree.children, to: root)
    }

    private func addChildren(_ items: [FileItem], to parent: GNode) {
        for item in items.prefix(60) where nodes[item.path] == nil {
            let n = GNode(item: item, parent: parent.id, near: parent.position)
            nodes[n.id] = n
            parent.children.append(n.id)
            edges.append((parent.id, n.id))
        }
        parent.expanded = true
    }

    // MARK: - Tap interactions

    /// Tap a folder: expand it. Tap again: collapse it. Tap a file: select it.
    func toggle(_ node: GNode) {
        selected = node
        loadRelated(node)
        guard node.item.isDir else { return }
        if node.expanded { collapse(node) } else { Task { await expand(node) } }
    }

    func expand(_ node: GNode) async {
        guard node.item.isDir, !node.expanded, nodes.count < maxNodes else { return }
        guard let tree: TreeResponse = try? await Backend.get("api/tree", ["path": node.id]) else { return }
        addChildren(tree.children, to: node)
        objectWillChange.send()
    }

    func collapse(_ node: GNode) {
        for childID in node.children {
            if let child = nodes[childID] {
                collapse(child)
                nodes.removeValue(forKey: childID)
            }
        }
        edges.removeAll { edge in nodes[edge.0] == nil || nodes[edge.1] == nil }
        node.children.removeAll()
        node.expanded = false
        objectWillChange.send()
    }

    func expandAll() {
        Task {
            var queue = nodes.values.filter { $0.item.isDir && !$0.expanded }
            var i = 0
            while i < queue.count, nodes.count < maxNodes {
                await expand(queue[i])
                queue.append(contentsOf: queue[i].children.compactMap { nodes[$0] }
                    .filter { $0.item.isDir && !$0.expanded })
                i += 1
            }
            if nodes.count >= maxNodes {
                statusText = "showing first \(maxNodes) nodes — tap folders to go deeper"
            }
        }
    }

    func minimizeAll() {
        guard let root = nodes[rootPath] else { return }
        for childID in root.children {
            if let child = nodes[childID], child.item.isDir, child.expanded {
                collapse(child)
            }
        }
        selected = nil
    }

    /// Expand ancestors so `path` exists in the graph, then select it.
    func reveal(_ path: String) async {
        guard path.hasPrefix(rootPath) else { return }
        let rel = path.dropFirst(rootPath.count).split(separator: "/").map(String.init)
        var current = rootPath
        for part in rel {
            if let n = nodes[current], n.item.isDir, !n.expanded { await expand(n) }
            current += "/" + part
        }
        if let n = nodes[path] {
            selected = n
            loadRelated(n)
        }
    }

    // MARK: - Physics

    private func step() {
        let all = Array(nodes.values)
        guard !all.isEmpty else { return }
        let damping: Float = reduceMotion ? 0.6 : 0.85
        let flatten = mode == .twoD

        for (a, b) in edges {
            guard let na = nodes[a], let nb = nodes[b] else { continue }
            let delta = nb.position - na.position
            let dist = max(simd_length(delta), 0.01)
            let want = na.radius + nb.radius + 55
            let f = (dist - want) * 0.02
            let dir = delta / dist
            na.velocity += dir * f
            nb.velocity -= dir * f
        }
        for i in 0..<all.count {
            for j in (i + 1)..<all.count {
                let delta = all[j].position - all[i].position
                let d2 = simd_length_squared(delta)
                if d2 > 40000 || d2 == 0 { continue }
                let d = sqrt(d2)
                let f = 340 / d2
                let dir = delta / d
                all[i].velocity -= dir * f
                all[j].velocity += dir * f
            }
        }
        for n in all {
            if n.pinned { n.velocity = .zero; continue }
            n.velocity *= damping
            n.position += n.velocity
            if flatten { n.position.z *= 0.85 }   // ease back to the plane in 2D
        }
        tick &+= 1
    }

    // MARK: - Backend calls

    func search(_ query: String, semantic: Bool) async {
        guard !query.isEmpty else { searchResults = []; return }
        let resp: SearchResponse? = try? await Backend.get(
            "api/search", ["q": query, "mode": semantic ? "semantic" : "keyword"])
        searchResults = resp?.results ?? []
    }

    func loadRelated(_ node: GNode) {
        related = nil
        guard !node.item.isDir else { return }
        Task {
            related = try? await Backend.get("api/related", ["path": node.id])
        }
    }

    func refreshRules() async {
        let resp: RulesResponse? = try? await Backend.get("api/rules")
        rules = resp?.rules ?? []
    }

    func setRule(prefix: String, allow: Bool) {
        Task {
            await Backend.post("api/rules", json: ["prefix": prefix, "allow": allow])
            await refreshRules()
            await refreshTreeAccessFlags()
        }
    }

    func deleteRule(_ id: Int) {
        Task {
            await Backend.delete("api/rules/\(id)")
            await refreshRules()
            await refreshTreeAccessFlags()
        }
    }

    /// Re-check allowed flags for visible nodes after a rule change.
    private func refreshTreeAccessFlags() async {
        for node in nodes.values where node.expanded {
            if let tree: TreeResponse = try? await Backend.get("api/tree", ["path": node.id]) {
                for item in tree.children {
                    nodes[item.path]?.item.allowed = item.allowed
                }
            }
        }
        objectWillChange.send()
    }

    func refreshStats() async {
        if let s: Stats = try? await Backend.get("api/stats") {
            statusText = "\(s.files.formatted()) files · \(s.embedded.formatted()) embedded"
        }
    }

    func rescan() {
        Task {
            await Backend.post("api/scan")
            statusText = "rescanning…"
            try? await Task.sleep(nanoseconds: 3_000_000_000)
            await refreshStats()
        }
    }
}
