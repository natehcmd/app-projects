import SwiftUI

/// The unified launcher shell: a left app-rail switches between Mission Control
/// (web) and Hands (native). Both render on the shared nate-default dark base.
struct RootShell: View {
    @State private var mode: Mode = .control

    enum Mode: String, CaseIterable, Identifiable {
        case control = "Control"
        case hands   = "Hands"
        var id: String { rawValue }
        var icon: String {
            switch self {
            case .control: return "square.grid.2x2.fill"
            case .hands:   return "hand.raised.fill"
            }
        }
    }

    var body: some View {
        HStack(spacing: 0) {
            rail
            content
        }
        .background(Theme.bg)
        .preferredColorScheme(.dark)
        .ignoresSafeArea()
    }

    private var rail: some View {
        VStack(spacing: 8) {
            ForEach(Mode.allCases) { m in
                RailButton(mode: m, selected: mode == m) {
                    withAnimation(.easeInOut(duration: 0.18)) { mode = m }
                }
            }
            Spacer()
        }
        .padding(.top, 38)
        .padding(.horizontal, 10)
        .padding(.bottom, 14)
        .frame(width: 78)
        .frame(maxHeight: .infinity)
        .background(Theme.bg2.opacity(0.6))
        .overlay(alignment: .trailing) {
            Rectangle().fill(Theme.glassBrd).frame(width: 1)
        }
    }

    @ViewBuilder
    private var content: some View {
        switch mode {
        case .control:
            ZStack {
                Theme.bg
                MCWebView(url: URL(string: "http://localhost:8450")!)
            }
        case .hands:
            ContentView()
        }
    }
}

private struct RailButton: View {
    let mode: RootShell.Mode
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Image(systemName: mode.icon)
                    .font(.system(size: 18, weight: .medium))
                Text(mode.rawValue)
                    .font(.system(size: 9, weight: .medium))
            }
            .frame(width: 58, height: 52)
            .foregroundStyle(selected ? Theme.bg : Theme.inkDim)
            .background(
                RoundedRectangle(cornerRadius: 15, style: .continuous)
                    .fill(selected ? AnyShapeStyle(Theme.mint)
                                   : AnyShapeStyle(Color.white.opacity(0.04)))
            )
        }
        .buttonStyle(.plain)
    }
}
