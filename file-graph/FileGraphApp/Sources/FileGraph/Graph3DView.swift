import SwiftUI
import SceneKit

struct Graph3DView: NSViewRepresentable {
    @ObservedObject var store: GraphStore

    func makeCoordinator() -> Coordinator { Coordinator(store: store) }

    func makeNSView(context: Context) -> SCNView {
        let view = SCNView()
        let scene = SCNScene()
        scene.background.contents = NSColor(
            red: 0.051, green: 0.059, blue: 0.078, alpha: 1)

        let camera = SCNCamera()
        camera.zFar = 4000
        let camNode = SCNNode()
        camNode.camera = camera
        camNode.position = SCNVector3(0, 0, 620)
        scene.rootNode.addChildNode(camNode)

        view.scene = scene
        view.allowsCameraControl = true          // orbit / pan / zoom with trackpad
        view.antialiasingMode = .multisampling4X
        view.rendersContinuously = true

        let click = NSClickGestureRecognizer(target: context.coordinator,
                                             action: #selector(Coordinator.click(_:)))
        view.addGestureRecognizer(click)
        context.coordinator.view = view
        context.coordinator.scene = scene
        context.coordinator.startSyncing()
        return view
    }

    func updateNSView(_ nsView: SCNView, context: Context) {}

    static func dismantleNSView(_ nsView: SCNView, coordinator: Coordinator) {
        coordinator.stopSyncing()
    }

    final class Coordinator: NSObject {
        let store: GraphStore
        weak var view: SCNView?
        var scene: SCNScene?
        private var spheres: [String: SCNNode] = [:]
        private var edgeNode: SCNNode?
        private var timer: Timer?

        init(store: GraphStore) { self.store = store }

        func startSyncing() {
            timer = Timer.scheduledTimer(withTimeInterval: 1.0 / 30.0, repeats: true) { [weak self] _ in
                Task { @MainActor in self?.sync() }
            }
        }

        func stopSyncing() { timer?.invalidate(); timer = nil }

        @MainActor
        func sync() {
            guard let scene else { return }
            var seen = Set<String>()
            for n in store.nodes.values {
                seen.insert(n.id)
                let sphere: SCNNode
                if let existing = spheres[n.id] {
                    sphere = existing
                } else {
                    let geom = SCNSphere(radius: CGFloat(n.radius) * 0.55)
                    geom.segmentCount = 16
                    let mat = SCNMaterial()
                    mat.lightingModel = .constant
                    sphere = SCNNode(geometry: geom)
                    sphere.name = n.id
                    scene.rootNode.addChildNode(sphere)
                    spheres[n.id] = sphere
                }
                let blocked = n.item.allowed == false
                let color = NSColor(blocked ? Palette.blocked : Palette.color(for: n.item.kind))
                sphere.geometry?.firstMaterial?.diffuse.contents = color
                sphere.geometry?.firstMaterial?.emission.contents =
                    color.withAlphaComponent(n.id == store.selected?.id ? 0.9 : 0.35)
                sphere.position = SCNVector3(n.position.x, -n.position.y, n.position.z)
            }
            for (id, node) in spheres where !seen.contains(id) {
                node.removeFromParentNode()
                spheres.removeValue(forKey: id)
            }
            rebuildEdges(in: scene)
        }

        @MainActor
        private func rebuildEdges(in scene: SCNScene) {
            edgeNode?.removeFromParentNode()
            var verts: [SCNVector3] = []
            var indices: [Int32] = []
            for (a, b) in store.edges {
                guard let na = store.nodes[a], let nb = store.nodes[b] else { continue }
                indices.append(Int32(verts.count)); verts.append(SCNVector3(na.position.x, -na.position.y, na.position.z))
                indices.append(Int32(verts.count)); verts.append(SCNVector3(nb.position.x, -nb.position.y, nb.position.z))
            }
            guard !verts.isEmpty else { return }
            let source = SCNGeometrySource(vertices: verts)
            let element = SCNGeometryElement(indices: indices, primitiveType: .line)
            let geom = SCNGeometry(sources: [source], elements: [element])
            let mat = SCNMaterial()
            mat.lightingModel = .constant
            mat.diffuse.contents = NSColor.white.withAlphaComponent(0.10)
            geom.materials = [mat]
            let node = SCNNode(geometry: geom)
            scene.rootNode.addChildNode(node)
            edgeNode = node
        }

        @MainActor @objc func click(_ g: NSClickGestureRecognizer) {
            guard let view else { return }
            let point = g.location(in: view)
            let hits = view.hitTest(point, options: [.searchMode: SCNHitTestSearchMode.closest.rawValue])
            if let path = hits.first?.node.name, let node = store.nodes[path] {
                store.toggle(node)
            }
        }
    }
}
