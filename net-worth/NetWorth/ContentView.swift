import SwiftUI

enum Tab: String, CaseIterable, Identifiable {
    case dashboard = "Dashboard"
    case accounts  = "Accounts"
    case budget    = "Budget"
    var id: String { rawValue }
    var icon: String {
        switch self {
        case .dashboard: return "chart.line.uptrend.xyaxis"
        case .accounts:  return "building.columns"
        case .budget:    return "creditcard"
        }
    }
    var accent: Color {
        switch self {
        case .dashboard: return Theme.mint
        case .accounts:  return Theme.lav
        case .budget:    return Theme.peach
        }
    }
}

struct ContentView: View {
    @State private var tab: Tab = .dashboard

    var body: some View {
        ZStack(alignment: .bottom) {
            OrbBackground()

            Group {
                switch tab {
                case .dashboard: DashboardView()
                case .accounts:  AccountsView()
                case .budget:    BudgetView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            .padding(.bottom, 84)   // clear the floating dock

            FloatingDock(tab: $tab)
                .padding(.bottom, 18)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .foregroundStyle(Theme.ink)
    }
}

// MARK: - Floating dock

struct FloatingDock: View {
    @Binding var tab: Tab

    var body: some View {
        HStack(spacing: 6) {
            ForEach(Tab.allCases) { t in
                let selected = t == tab
                Button {
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) { tab = t }
                } label: {
                    HStack(spacing: 8) {
                        Image(systemName: t.icon)
                            .font(.system(size: 14, weight: .semibold))
                        if selected {
                            Text(t.rawValue)
                                .font(.system(size: 13, weight: .semibold))
                                .transition(.opacity.combined(with: .move(edge: .leading)))
                        }
                    }
                    .foregroundStyle(selected ? Theme.bg : Theme.inkDim)
                    .padding(.horizontal, selected ? 16 : 13)
                    .padding(.vertical, 10)
                    .background(
                        RoundedRectangle(cornerRadius: 13, style: .continuous)
                            .fill(selected ? t.accent : Color.clear)
                    )
                }
                .buttonStyle(.plain)
            }
        }
        .padding(6)
        .background(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .strokeBorder(Theme.glassBrd, lineWidth: 1)
                )
        )
        .shadow(color: .black.opacity(0.4), radius: 18, y: 8)
    }
}

// MARK: - Reusable header

struct ScreenHeader: View {
    let title: String
    let subtitle: String
    var accent: Color = Theme.mint

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title)
                .font(.system(size: 26, weight: .bold))
                .foregroundStyle(Theme.ink)
            Text(subtitle)
                .font(.system(size: 13))
                .foregroundStyle(Theme.inkDim)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

#Preview {
    ContentView().environmentObject(Store()).frame(width: 1000, height: 700)
}
