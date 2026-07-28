import SwiftUI
import Charts

struct DashboardView: View {
    @EnvironmentObject var store: Store

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                ScreenHeader(title: "Net Worth",
                             subtitle: "Your complete financial picture, fully local.")

                // Big net-worth number
                netWorthCard

                // Assets vs liabilities split
                HStack(spacing: 14) {
                    statTile("Assets", store.totalAssets, Theme.mint, "arrow.up.right")
                    statTile("Liabilities", store.totalLiabilities, Theme.rose, "arrow.down.right")
                }

                // Trend chart
                trendCard
            }
            .padding(28)
            .frame(maxWidth: 900, alignment: .leading)
            .frame(maxWidth: .infinity)
        }
    }

    private var netWorthCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("TOTAL NET WORTH")
                    .font(.system(size: 11, weight: .bold))
                    .tracking(1.4)
                    .foregroundStyle(Theme.inkDim)
                Spacer()
                Button {
                    withAnimation { store.recordSnapshot() }
                } label: {
                    Label("Record snapshot", systemImage: "camera.aperture")
                        .font(.system(size: 12, weight: .semibold))
                        .padding(.horizontal, 12).padding(.vertical, 7)
                        .background(RoundedRectangle(cornerRadius: 10, style: .continuous).fill(Theme.mint))
                        .foregroundStyle(Theme.bg)
                }
                .buttonStyle(.plain)
            }
            Text(store.netWorth.asCurrency)
                .font(.system(size: 52, weight: .bold, design: .rounded))
                .foregroundStyle(Theme.ink)
            if let change = monthChange {
                Label(change.text, systemImage: change.up ? "arrow.up.right" : "arrow.down.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(change.up ? Theme.mint : Theme.rose)
            }
        }
        .padding(22)
        .frame(maxWidth: .infinity, alignment: .leading)
        .glassCard(radius: 18)
    }

    private func statTile(_ label: String, _ value: Double, _ color: Color, _ icon: String) -> some View {
        HStack(spacing: 14) {
            Image(systemName: icon)
                .font(.system(size: 18, weight: .semibold))
                .foregroundStyle(color)
                .frame(width: 40, height: 40)
                .background(Circle().fill(color.opacity(0.14)))
            VStack(alignment: .leading, spacing: 2) {
                Text(label).font(.system(size: 12)).foregroundStyle(Theme.inkDim)
                Text(value.asCurrency).font(.system(size: 22, weight: .bold)).foregroundStyle(Theme.ink)
            }
            Spacer()
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .glassCard(radius: 16)
    }

    private var trendCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Trend Over Time")
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(Theme.ink)

            if store.db.snapshots.count < 2 {
                Text("Record a couple of snapshots to see your trend.")
                    .font(.system(size: 13)).foregroundStyle(Theme.inkDim)
                    .frame(maxWidth: .infinity, minHeight: 200)
            } else {
                Chart(store.db.snapshots) { s in
                    AreaMark(x: .value("Date", s.date),
                             y: .value("Net Worth", s.netWorth))
                        .interpolationMethod(.catmullRom)
                        .foregroundStyle(.linearGradient(
                            colors: [Theme.mint.opacity(0.35), Theme.mint.opacity(0.02)],
                            startPoint: .top, endPoint: .bottom))
                    LineMark(x: .value("Date", s.date),
                             y: .value("Net Worth", s.netWorth))
                        .interpolationMethod(.catmullRom)
                        .foregroundStyle(Theme.mint)
                        .lineStyle(StrokeStyle(lineWidth: 2.5))
                    PointMark(x: .value("Date", s.date),
                              y: .value("Net Worth", s.netWorth))
                        .foregroundStyle(Theme.mint)
                        .symbolSize(28)
                }
                .chartYAxis {
                    AxisMarks { v in
                        AxisGridLine().foregroundStyle(Theme.glassBrd)
                        AxisValueLabel {
                            if let d = v.as(Double.self) { Text(d.asCurrency).foregroundStyle(Theme.inkDim) }
                        }
                    }
                }
                .chartXAxis {
                    AxisMarks(values: .automatic(desiredCount: 5)) { _ in
                        AxisGridLine().foregroundStyle(Theme.glassBrd.opacity(0.5))
                        AxisValueLabel(format: .dateTime.month(.abbreviated).day())
                            .foregroundStyle(Theme.inkDim)
                    }
                }
                .frame(height: 240)
            }
        }
        .padding(22)
        .frame(maxWidth: .infinity, alignment: .leading)
        .glassCard(radius: 18)
    }

    private var monthChange: (text: String, up: Bool)? {
        let snaps = store.db.snapshots.sorted { $0.date < $1.date }
        guard let last = snaps.last, snaps.count >= 2 else { return nil }
        let prev = snaps[snaps.count - 2].netWorth
        let diff = last.netWorth - prev
        guard prev != 0 else { return nil }
        let pct = diff / abs(prev) * 100
        let sign = diff >= 0 ? "+" : "−"
        return ("\(sign)\(abs(diff).asCurrency)  (\(String(format: "%.1f", abs(pct)))%) since last snapshot", diff >= 0)
    }
}
