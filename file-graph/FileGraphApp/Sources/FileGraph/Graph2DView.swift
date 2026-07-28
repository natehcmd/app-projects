import SwiftUI
import simd

struct Graph2DView: View {
    @ObservedObject var store: GraphStore
    @State private var pan = CGSize.zero
    @State private var panStart = CGSize.zero
    @State private var zoom: CGFloat = 1
    @State private var hovered: String?

    var body: some View {
        GeometryReader { geo in
            Canvas { ctx, size in
                _ = store.tick   // subscribe to simulation frames
                let center = CGPoint(x: size.width / 2 + pan.width,
                                     y: size.height / 2 + pan.height)
                func screen(_ n: GNode) -> CGPoint {
                    CGPoint(x: center.x + CGFloat(n.position.x) * zoom,
                            y: center.y + CGFloat(n.position.y) * zoom)
                }

                var edgePath = Path()
                for (a, b) in store.edges {
                    guard let na = store.nodes[a], let nb = store.nodes[b] else { continue }
                    edgePath.move(to: screen(na))
                    edgePath.addLine(to: screen(nb))
                }
                ctx.stroke(edgePath, with: .color(.white.opacity(0.08)), lineWidth: 1)

                for n in store.nodes.values {
                    let p = screen(n)
                    let r = CGFloat(n.radius) * zoom
                    let rect = CGRect(x: p.x - r, y: p.y - r, width: r * 2, height: r * 2)
                    let blockedNode = n.item.allowed == false
                    let color = blockedNode ? Palette.blocked : Palette.color(for: n.item.kind)
                    ctx.fill(Circle().path(in: rect),
                             with: .color(color.opacity(n.item.isDir ? 0.9 : 0.6)))
                    if n.id == store.selected?.id || n.id == hovered {
                        ctx.stroke(Circle().path(in: rect.insetBy(dx: -2, dy: -2)),
                                   with: .color(.white), lineWidth: 1.5)
                    }
                    if blockedNode {
                        ctx.draw(Text("🔒").font(.system(size: max(8, r))), at: p)
                    }
                    if n.item.isDir || n.id == store.selected?.id || n.id == hovered || zoom > 1.6 {
                        ctx.draw(Text(String(n.item.name.prefix(24)))
                                    .font(.system(size: 10))
                                    .foregroundStyle(.white.opacity(0.85)),
                                 at: CGPoint(x: p.x, y: p.y + r + 10))
                    }
                }
            }
            .background(Palette.background)
            .contentShape(Rectangle())
            .gesture(
                SpatialTapGesture().onEnded { value in
                    if let n = hit(value.location, in: geo.size) { store.toggle(n) }
                }
            )
            .gesture(
                DragGesture(minimumDistance: 2)
                    .onChanged { v in
                        pan = CGSize(width: panStart.width + v.translation.width,
                                     height: panStart.height + v.translation.height)
                    }
                    .onEnded { _ in panStart = pan }
            )
            .gesture(
                MagnifyGesture().onChanged { v in
                    zoom = min(4, max(0.15, zoom * v.magnification))
                }
            )
            .onContinuousHover { phase in
                if case .active(let loc) = phase { hovered = hit(loc, in: geo.size)?.id }
                else { hovered = nil }
            }
        }
    }

    private func hit(_ loc: CGPoint, in size: CGSize) -> GNode? {
        let gx = Float((loc.x - size.width / 2 - pan.width) / zoom)
        let gy = Float((loc.y - size.height / 2 - pan.height) / zoom)
        var best: GNode?
        var bestDist: Float = .infinity
        for n in store.nodes.values {
            let d = simd_length(SIMD2(n.position.x - gx, n.position.y - gy))
            if d < n.radius + 8, d < bestDist { best = n; bestDist = d }
        }
        return best
    }
}
