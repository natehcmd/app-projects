import SwiftUI

/// nate-default design tokens — dark-first, pastel accents, glass surfaces.
/// This is the canonical copy: the same token set is mirrored into
/// net-worth, my-apps, and unified-os so every app shares one look. If you
/// change a value here, it's worth carrying the change to those too.
enum Theme {
    // Base
    static let bg       = Color(hex: 0x0b0d12)
    static let bg2      = Color(hex: 0x11141c)
    static let ink      = Color(hex: 0xe8eaf2)
    static let inkDim   = Color(hex: 0x9aa0b4)
    static let inkFaint = Color(hex: 0x5c6275)
    // Pastel accents
    static let mint  = Color(hex: 0x9fe8c9)
    static let lav   = Color(hex: 0xc3b8f5)
    static let peach = Color(hex: 0xf5c9a8)
    static let rose  = Color(hex: 0xf2a9c4)
    static let sky   = Color(hex: 0xa8d8f5)
    // Glass
    static let glass    = Color.white.opacity(0.045)
    static let glassBrd = Color.white.opacity(0.09)

    static let radius: CGFloat = 18

    /// Not part of the shared palette (the pastels read as too soft for an
    /// error state) — a warmer, more saturated coral kept in the same
    /// light/pastel range so it still feels like part of the family.
    static let alert = Color(hex: 0xf28a8a)
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
