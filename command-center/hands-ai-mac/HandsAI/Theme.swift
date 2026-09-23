import SwiftUI

// Stark HUD palette — same values as command-center/mission-control/static/stark.css.

/// nate-default design tokens — dark-first, pastel accents, glass surfaces.
/// This is the canonical copy: the same token set is mirrored into
/// net-worth, my-apps, and unified-os so every app shares one look. If you
/// change a value here, it's worth carrying the change to those too.
enum Theme {
    // Base
    static let bg       = Color(hex: 0x02070d)
    static let bg2      = Color(hex: 0x06121e)
    static let ink      = Color(hex: 0xdff6ff)
    static let inkDim   = Color(hex: 0x86a9bf)
    static let inkFaint = Color(hex: 0x4d6a7e)
    // Pastel accents
    static let mint  = Color(hex: 0x39e6ff)
    static let lav   = Color(hex: 0x6fa8ff)
    static let peach = Color(hex: 0xffb347)
    static let rose  = Color(hex: 0xff4d6d)
    static let sky   = Color(hex: 0x39c4ff)
    // Glass
    static let glass    = Color(hex: 0x0a2238).opacity(0.55)
    static let glassBrd = Color(hex: 0x39c4ff).opacity(0.22)

    static let radius: CGFloat = 8   // Stark HUD: tight corners, shared with stark.css (--r)

    /// Not part of the shared palette (the pastels read as too soft for an
    /// error state) — a warmer, more saturated coral kept in the same
    /// light/pastel range so it still feels like part of the family.
    static let alert = Color(hex: 0xff4d6d)
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

/// Glass card surface — the look every card/bubble/panel in the app shares.
struct GlassCard: ViewModifier {
    var radius: CGFloat = 14
    func body(content: Content) -> some View {
        content
            .background(
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .fill(Theme.glass)
            )
            .overlay(
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .strokeBorder(Theme.glassBrd, lineWidth: 1)
            )
    }
}

extension View {
    func glassCard(radius: CGFloat = 14) -> some View {
        modifier(GlassCard(radius: radius))
    }
}
