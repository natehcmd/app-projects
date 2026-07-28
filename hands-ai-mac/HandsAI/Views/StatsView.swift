import SwiftUI

struct StatsView: View {
    @EnvironmentObject var stats: StatsService

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                HeaderCard()
                HStack(spacing: 12) {
                    CPUCard()
                    MemoryCard()
                }
                HStack(spacing: 12) {
                    DiskCard()
                    NetworkCard()
                }
                ThermalBatteryCard()
                CoresCard()
                ProcessesCard()
            }
            .padding(14)
        }
    }
}

// MARK: - Cards

private struct StatCard<Content: View>: View {
    let title: String
    let symbol: String
    let accent: Color
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: symbol)
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(accent)
                Text(title)
                    .font(.system(size: 10, weight: .semibold, design: .rounded))
                    .foregroundStyle(.secondary)
                    .textCase(.uppercase)
            }
            content()
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(Color.black.opacity(0.22))
                .overlay(
                    RoundedRectangle(cornerRadius: 14, style: .continuous)
                        .strokeBorder(.white.opacity(0.06), lineWidth: 1)
                )
        )
    }
}

private struct HeaderCard: View {
    @EnvironmentObject var stats: StatsService

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(stats.stats.hostName)
                    .font(.system(size: 15, weight: .semibold, design: .rounded))
                Text(stats.stats.osVersion)
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundStyle(.secondary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text("Uptime")
                    .font(.system(size: 9, weight: .semibold, design: .rounded))
                    .foregroundStyle(.tertiary)
                    .textCase(.uppercase)
                Text(formatUptime(stats.stats.uptimeSeconds))
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(Color.black.opacity(0.22))
                .overlay(
                    RoundedRectangle(cornerRadius: 14, style: .continuous)
                        .strokeBorder(.white.opacity(0.06), lineWidth: 1)
                )
        )
    }

    private func formatUptime(_ s: TimeInterval) -> String {
        let days = Int(s) / 86400
        let hours = (Int(s) % 86400) / 3600
        let mins = (Int(s) % 3600) / 60
        if days > 0 { return "\(days)d \(hours)h \(mins)m" }
        if hours > 0 { return "\(hours)h \(mins)m" }
        return "\(mins)m"
    }
}

private struct CPUCard: View {
    @EnvironmentObject var stats: StatsService
    var body: some View {
        StatCard(title: "CPU", symbol: "cpu", accent: .blue) {
            HStack(alignment: .firstTextBaseline) {
                Text(String(format: "%.0f", stats.stats.cpuPercent))
                    .font(.system(size: 32, weight: .light, design: .rounded))
                Text("%")
                    .font(.system(size: 12, design: .rounded))
                    .foregroundStyle(.secondary)
                Spacer()
            }
            SparkLine(values: stats.cpuHistory, max: 100, color: .blue)
                .frame(height: 30)
        }
    }
}

private struct MemoryCard: View {
    @EnvironmentObject var stats: StatsService
    var body: some View {
        StatCard(title: "Memory", symbol: "memorychip", accent: .teal) {
            HStack(alignment: .firstTextBaseline) {
                Text(String(format: "%.1f", stats.stats.ramUsedGB))
                    .font(.system(size: 32, weight: .light, design: .rounded))
                Text("/ \(String(format: "%.0f", stats.stats.ramTotalGB)) GB")
                    .font(.system(size: 11, design: .rounded))
                    .foregroundStyle(.secondary)
                Spacer()
            }
            SparkLine(values: stats.ramHistory, max: 100, color: .teal)
                .frame(height: 30)
            if stats.stats.swapUsedGB > 0.05 {
                Text(String(format: "swap %.2f GB", stats.stats.swapUsedGB))
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundStyle(.tertiary)
            }
        }
    }
}

private struct DiskCard: View {
    @EnvironmentObject var stats: StatsService
    var body: some View {
        StatCard(title: "Disk", symbol: "internaldrive", accent: .yellow) {
            HStack(alignment: .firstTextBaseline) {
                Text(String(format: "%.0f", stats.stats.diskFreeGB))
                    .font(.system(size: 32, weight: .light, design: .rounded))
                Text("GB free")
                    .font(.system(size: 11, design: .rounded))
                    .foregroundStyle(.secondary)
                Spacer()
            }
            ProgressBar(value: stats.stats.diskUsedFraction, color: .yellow)
                .frame(height: 6)
            Text(String(format: "%.0f / %.0f GB", stats.stats.diskTotalGB - stats.stats.diskFreeGB, stats.stats.diskTotalGB))
                .font(.system(size: 9, design: .monospaced))
                .foregroundStyle(.tertiary)
        }
    }
}

private struct NetworkCard: View {
    @EnvironmentObject var stats: StatsService
    var body: some View {
        StatCard(title: "Network", symbol: "network", accent: .green) {
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 2) {
                    Label(formatRate(stats.stats.netDownKBps), systemImage: "arrow.down")
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(.primary)
                    Label(formatRate(stats.stats.netUpKBps), systemImage: "arrow.up")
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(.secondary)
                }
                Spacer()
                VStack {
                    SparkLine(values: stats.netDownHistory, max: max(100, stats.netDownHistory.max() ?? 100), color: .green)
                        .frame(height: 14)
                    SparkLine(values: stats.netUpHistory, max: max(100, stats.netUpHistory.max() ?? 100), color: .green.opacity(0.6))
                        .frame(height: 14)
                }
                .frame(width: 90)
            }
        }
    }

    private func formatRate(_ kbps: Double) -> String {
        if kbps > 1024 { return String(format: "%.2f MB/s", kbps / 1024) }
        return String(format: "%.0f KB/s", kbps)
    }
}

private struct ThermalBatteryCard: View {
    @EnvironmentObject var stats: StatsService
    var body: some View {
        StatCard(title: "Thermal · Power", symbol: "thermometer.medium", accent: .orange) {
            HStack(spacing: 18) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Thermal")
                        .font(.system(size: 9, weight: .semibold, design: .rounded))
                        .foregroundStyle(.tertiary).textCase(.uppercase)
                    Text(stats.stats.thermalLevel)
                        .font(.system(size: 13, weight: .medium, design: .rounded))
                        .foregroundStyle(thermalColor)
                }
                Divider().frame(height: 28)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Battery")
                        .font(.system(size: 9, weight: .semibold, design: .rounded))
                        .foregroundStyle(.tertiary).textCase(.uppercase)
                    if let pct = stats.stats.batteryPercent {
                        HStack(spacing: 4) {
                            Text(String(format: "%.0f%%", pct))
                                .font(.system(size: 13, weight: .medium, design: .rounded))
                            if stats.stats.batteryCharging {
                                Image(systemName: "bolt.fill")
                                    .font(.system(size: 10))
                                    .foregroundStyle(.green)
                            }
                        }
                    } else {
                        Text("Desktop")
                            .font(.system(size: 12, design: .rounded))
                            .foregroundStyle(.secondary)
                    }
                }
                Spacer()
            }
        }
    }

    private var thermalColor: Color {
        switch stats.stats.thermalLevel {
        case "Nominal":  return .green
        case "Fair":     return .yellow
        case "Serious":  return .orange
        case "Critical": return .red
        default:         return .secondary
        }
    }
}

private struct CoresCard: View {
    @EnvironmentObject var stats: StatsService
    var body: some View {
        StatCard(title: "Cores", symbol: "square.grid.3x3.fill", accent: .purple) {
            let cores = stats.stats.perCore
            if cores.isEmpty {
                Text("sampling…")
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(.tertiary)
            } else {
                LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 4), count: min(8, cores.count)), spacing: 4) {
                    ForEach(Array(cores.enumerated()), id: \.offset) { _, value in
                        CoreBar(value: value)
                    }
                }
            }
        }
    }
}

private struct CoreBar: View {
    let value: Double
    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .bottom) {
                RoundedRectangle(cornerRadius: 3).fill(Color.white.opacity(0.06))
                RoundedRectangle(cornerRadius: 3)
                    .fill(LinearGradient(colors: [.purple.opacity(0.5), .purple], startPoint: .bottom, endPoint: .top))
                    .frame(height: max(2, geo.size.height * value / 100))
            }
        }
        .frame(height: 26)
    }
}

private struct ProcessesCard: View {
    @EnvironmentObject var stats: StatsService
    var body: some View {
        StatCard(title: "Top processes", symbol: "list.bullet.rectangle", accent: .pink) {
            VStack(spacing: 2) {
                ForEach(stats.stats.topProcesses.prefix(8)) { row in
                    HStack(spacing: 8) {
                        Text(row.name)
                            .font(.system(size: 11, design: .monospaced))
                            .lineLimit(1)
                            .truncationMode(.tail)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        Text(String(format: "%.0f%%", row.cpu))
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundStyle(.secondary)
                            .frame(width: 48, alignment: .trailing)
                        Text(String(format: "%.0f MB", row.memMB))
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundStyle(.tertiary)
                            .frame(width: 72, alignment: .trailing)
                    }
                    .padding(.vertical, 1)
                }
            }
        }
    }
}

// MARK: - Sparkline + Progress

struct SparkLine: View {
    let values: [Double]
    let max: Double
    let color: Color

    var body: some View {
        GeometryReader { geo in
            ZStack {
                line(geo: geo)
                fill(geo: geo)
            }
        }
    }

    private func line(geo: GeometryProxy) -> some View {
        Path { path in
            guard values.count > 1 else { return }
            let w = geo.size.width
            let h = geo.size.height
            let step = w / CGFloat(values.count - 1)
            for (i, v) in values.enumerated() {
                let x = CGFloat(i) * step
                let y = h - CGFloat(v / max) * h
                if i == 0 { path.move(to: CGPoint(x: x, y: y)) }
                else { path.addLine(to: CGPoint(x: x, y: y)) }
            }
        }
        .stroke(color, style: StrokeStyle(lineWidth: 1.4, lineCap: .round, lineJoin: .round))
    }

    private func fill(geo: GeometryProxy) -> some View {
        Path { path in
            guard values.count > 1 else { return }
            let w = geo.size.width
            let h = geo.size.height
            let step = w / CGFloat(values.count - 1)
            path.move(to: CGPoint(x: 0, y: h))
            for (i, v) in values.enumerated() {
                let x = CGFloat(i) * step
                let y = h - CGFloat(v / max) * h
                path.addLine(to: CGPoint(x: x, y: y))
            }
            path.addLine(to: CGPoint(x: w, y: h))
            path.closeSubpath()
        }
        .fill(LinearGradient(colors: [color.opacity(0.25), color.opacity(0.01)],
                             startPoint: .top, endPoint: .bottom))
    }
}

struct ProgressBar: View {
    let value: Double // 0..1
    let color: Color
    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule().fill(Color.white.opacity(0.06))
                Capsule()
                    .fill(LinearGradient(colors: [color.opacity(0.7), color], startPoint: .leading, endPoint: .trailing))
                    .frame(width: geo.size.width * value)
            }
        }
    }
}
