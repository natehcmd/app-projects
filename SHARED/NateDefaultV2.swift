import SwiftUI

/// nate-default v2 — restrained token set. Swift mirror of nate-default-v2.css.
/// Replaces the v1 "glass + orbs + 5 neon accents" look flagged Tier 1 by the
/// 2026-09-06 sellable-vs-slop audit.
///
/// Rules: one accent, one gray family, no orb backdrop, no glow, glass only
/// where elevation means something, a real spacing scale, monospaced digits on
/// numbers, motion = feedback only.
enum ThemeV2 {
    // Ground + surfaces (cool neutrals, single temperature; not pure black)
    static let bg        = Color(hex: 0x0d0f13)
    static let surface1  = Color(hex: 0x14171d)
    static let surface2  = Color(hex: 0x1b1f27)
    static let border    = Color(hex: 0x262b35)

    // Ink — one gray family
    static let ink       = Color(hex: 0xe9ebf0)
    static let inkDim    = Color(hex: 0x9ba1af)
    static let inkFaint  = Color(hex: 0x6b7280)

    // One accent (override per app). Default: calm blue-cyan.
    static let accent    = Color(hex: 0x4aa3d4)
    static let accentInk = Color(hex: 0x06121a)

    // Semantic status — used sparingly, never as the accent
    static let ok   = Color(hex: 0x4ea87b)
    static let warn = Color(hex: 0xd9a441)
    static let err  = Color(hex: 0xd96a6a)

    // Spacing scale
    static let s1: CGFloat = 4;  static let s2: CGFloat = 8
    static let s3: CGFloat = 12; static let s4: CGFloat = 16
    static let s6: CGFloat = 24; static let s8: CGFloat = 32

    static let rSm: CGFloat = 8
    static let rMd: CGFloat = 12
}

/// Drop this init only if the target's existing Theme file doesn't already
/// define `Color(hex: UInt32)` — keeping both is a redeclaration error.
extension Color {
    init(hex: UInt32) {
        self.init(.sRGB,
                  red:   Double((hex >> 16) & 0xff) / 255,
                  green: Double((hex >> 8)  & 0xff) / 255,
                  blue:  Double(hex & 0xff) / 255,
                  opacity: 1)
    }
}

/// A genuinely-elevated surface. Use only where elevation carries hierarchy —
/// not as the default background for every row/section.
struct RaisedCard: ViewModifier {
    var radius: CGFloat = ThemeV2.rMd
    func body(content: Content) -> some View {
        content
            .background(RoundedRectangle(cornerRadius: radius, style: .continuous).fill(ThemeV2.surface1))
            .overlay(RoundedRectangle(cornerRadius: radius, style: .continuous).strokeBorder(ThemeV2.border, lineWidth: 1))
    }
}
extension View {
    func raisedCard(radius: CGFloat = ThemeV2.rMd) -> some View { modifier(RaisedCard(radius: radius)) }
    /// Apply to every Text that shows a number that lines up in a column.
    func tnum() -> some View { self.monospacedDigit() }
}

/// Plain ground. No orbs. (v1's OrbBackground is intentionally not ported.)
struct GroundV2: View {
    var body: some View { ThemeV2.bg.ignoresSafeArea() }
}
