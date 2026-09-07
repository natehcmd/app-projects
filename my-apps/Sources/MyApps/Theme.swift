import SwiftUI

/// nate-default design tokens — dark-first, vibrant pastel accents, glass surfaces.
enum Theme {
    // Base
    static let bg       = Color(hex: 0x0b0d12)
    static let bg2      = Color(hex: 0x11141c)
    static let ink      = Color(hex: 0xe8eaf2)
    static let inkDim   = Color(hex: 0x9aa0b4)
    static let inkFaint = Color(hex: 0x5c6275)
    
    // Vibrant pastel palette for unique app styling
    static let mint    = Color(hex: 0x6ee7b7)
    static let lav     = Color(hex: 0xc4b5fd)
    static let peach   = Color(hex: 0xfdba74)
    static let rose    = Color(hex: 0xf472b6)
    static let sky     = Color(hex: 0x38bdf8)
    static let emerald = Color(hex: 0x34d399)
    static let violet  = Color(hex: 0xa78bfa)
    static let amber   = Color(hex: 0xfbbf24)
    static let cyan    = Color(hex: 0x22d3ee)
    static let indigo  = Color(hex: 0x818cf8)
    static let coral   = Color(hex: 0xfb7185)
    static let teal    = Color(hex: 0x2dd4bf)

    static let radius: CGFloat = 18
    static let glass    = Color.white.opacity(0.05)
    static let glassBrd = Color.white.opacity(0.10)

    static let palette: [Color] = [mint, lav, peach, rose, sky, emerald, violet, amber, cyan, indigo, coral, teal]
    
    /// Deterministic unique color for any app key
    static func color(for key: String) -> Color {
        let idx = abs(key.hashValue) % palette.count
        return palette[idx]
    }

    /// Secondary complement color for gradients
    static func secondaryColor(for key: String) -> Color {
        let idx = (abs(key.hashValue) + 3) % palette.count
        return palette[idx]
    }

    /// Unique gradient per app
    static func gradient(for key: String) -> LinearGradient {
        LinearGradient(
            colors: [color(for: key).opacity(0.28), secondaryColor(for: key).opacity(0.12)],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }

    /// Dynamic icon glyph selection per app
    static func icon(for app: MadeApp) -> String {
        let name = app.name.lowercased()
        if name.contains("code") || name.contains("graph") || name.contains("map") { return "curlybraces" }
        if name.contains("ad") || name.contains("market") || name.contains("lead") { return "chart.bar.fill" }
        if name.contains("resume") || name.contains("job") || name.contains("cert") { return "doc.text.fill" }
        if name.contains("rag") || name.contains("search") || name.contains("find") { return "magnifyingglass" }
        if name.contains("design") || name.contains("ui") || name.contains("vibe") { return "paintpalette.fill" }
        if name.contains("scan") || name.contains("guard") || name.contains("slop") { return "shield.checkerboard" }
        if name.contains("jarvis") || name.contains("voice") || name.contains("ai") { return "brain.head.profile" }
        
        let icons = ["sparkles", "terminal.fill", "cpu.fill", "bolt.fill", "command", "wand.and.stars", "app.fill", "cube.fill"]
        return icons[abs(app.name.hashValue) % icons.count]
    }
}

extension Color {
    init(hex: UInt32) {
        self.init(
            .sRGB,
            red:   Double((hex >> 16) & 0xff) / 255,
            green: Double((hex >> 8)  & 0xff) / 255,
            blue:  Double(hex & 0xff) / 255,
            opacity: 1
        )
    }
}

struct GlassCard: ViewModifier {
    var radius: CGFloat = 14
    func body(content: Content) -> some View {
        // Solid raised surface, not translucent "glass". (2026-09-06 audit:
        // glass-on-everything reads Tier 1.) Elevation is the border + a
        // single tinted-toward-ground shadow, not blur.
        content
            .background(
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .fill(Theme.bg2)
            )
            .overlay(
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .strokeBorder(Color.white.opacity(0.07), lineWidth: 1)
            )
    }
}

extension View {
    func glassCard(radius: CGFloat = 14) -> some View {
        modifier(GlassCard(radius: radius))
    }
}

/// Plain ground. The blurred pastel orb backdrop was removed 2026-09-06
/// (audit: orb backdrop reads Tier 1). Kept as a named view so call sites
/// don't change.
struct OrbBackground: View {
    var body: some View {
        Theme.bg.ignoresSafeArea()
    }
}
