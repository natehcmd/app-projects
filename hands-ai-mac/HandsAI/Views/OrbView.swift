import SwiftUI

struct OrbView: View {
    let state: AgentState
    @State private var phase: Double = 0

    var body: some View {
        TimelineView(.animation) { context in
            let t = context.date.timeIntervalSinceReferenceDate
            ZStack {
                outerGlow(t: t)
                innerCore(t: t)
                particles(t: t)
                centerSymbol
            }
            .compositingGroup()
            .animation(.easeInOut(duration: 0.5), value: state)
        }
        .frame(width: 200, height: 200)
    }

    // MARK: - Layers

    private func outerGlow(t: TimeInterval) -> some View {
        let pulse = 0.5 + 0.5 * sin(t * pulseSpeed)
        return Circle()
            .fill(
                RadialGradient(
                    colors: [
                        state.tint.opacity(0.55),
                        state.tint.opacity(0.18),
                        .clear,
                    ],
                    center: .center,
                    startRadius: 20,
                    endRadius: 110
                )
            )
            .scaleEffect(0.96 + 0.06 * pulse)
            .blur(radius: 14)
    }

    private func innerCore(t: TimeInterval) -> some View {
        let pulse = 0.5 + 0.5 * sin(t * pulseSpeed * 1.4)
        return ZStack {
            Circle()
                .fill(
                    LinearGradient(
                        colors: [
                            state.tint.opacity(0.85),
                            state.tint.opacity(0.45),
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .frame(width: 96, height: 96)
                .blur(radius: 0.6)
                .overlay(
                    Circle()
                        .strokeBorder(.white.opacity(0.20), lineWidth: 1)
                )

            // Highlight specular
            Circle()
                .fill(
                    LinearGradient(
                        colors: [.white.opacity(0.45), .clear],
                        startPoint: .top,
                        endPoint: .center
                    )
                )
                .frame(width: 72, height: 72)
                .offset(y: -10)
                .blendMode(.screen)
                .opacity(0.6 + 0.4 * pulse)
        }
    }

    private func particles(t: TimeInterval) -> some View {
        Canvas { ctx, size in
            let center = CGPoint(x: size.width / 2, y: size.height / 2)
            let count = particleCount
            for i in 0..<count {
                let phase = (Double(i) / Double(count)) * .pi * 2
                let speed = orbitSpeed
                let radius = orbitRadius(i: i, t: t)
                let x = center.x + cos(t * speed + phase) * radius
                let y = center.y + sin(t * speed + phase) * radius
                let alpha = 0.35 + 0.4 * (0.5 + 0.5 * sin(t * 2 + phase * 3))
                let dot = Path(ellipseIn: CGRect(x: x - 1.6, y: y - 1.6, width: 3.2, height: 3.2))
                ctx.fill(dot, with: .color(state.tint.opacity(alpha)))
            }
        }
        .frame(width: 200, height: 200)
        .opacity(particleOpacity)
        .blendMode(.plusLighter)
    }

    private var centerSymbol: some View {
        Image(systemName: state.symbol)
            .font(.system(size: 28, weight: .medium))
            .foregroundStyle(.white.opacity(0.92))
            .shadow(color: state.tint.opacity(0.8), radius: 8)
    }

    // MARK: - State tuning

    private var pulseSpeed: Double {
        switch state {
        case .idle:      return 1.4
        case .listening: return 5.0
        case .thinking:  return 3.2
        case .speaking:  return 4.0
        case .error:     return 2.0
        default:         return 2.6
        }
    }

    private var particleCount: Int {
        switch state {
        case .idle:      return 12
        case .listening: return 24
        case .thinking:  return 40
        case .speaking:  return 30
        default:         return 20
        }
    }

    private var particleOpacity: Double {
        switch state {
        case .idle:      return 0.35
        case .thinking:  return 1.0
        case .listening: return 0.85
        case .speaking:  return 0.85
        case .error:     return 0.5
        default:         return 0.7
        }
    }

    private var orbitSpeed: Double {
        switch state {
        case .thinking:  return 1.4
        case .speaking:  return 1.1
        case .listening: return 1.8
        default:         return 0.5
        }
    }

    private func orbitRadius(i: Int, t: TimeInterval) -> CGFloat {
        let base: Double = {
            switch state {
            case .thinking: return 70
            case .speaking: return 62
            case .listening: return 58
            default: return 56
            }
        }()
        let wobble = sin(t * 1.2 + Double(i)) * 6
        return CGFloat(base + wobble)
    }
}

#Preview {
    OrbView(state: .thinking)
        .frame(width: 300, height: 300)
        .background(.black)
}
