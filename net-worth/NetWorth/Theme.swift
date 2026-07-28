import SwiftUI

/// nate-default design tokens — dark-first, pastel accents, glass surfaces.
/// Copied from Hands AI so every app Nate ships shares one look.
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

    /// Stable pastel color for a spending category (by hash).
    static let palette: [Color] = [mint, lav, peach, rose, sky]
    static func color(for key: String) -> Color {
        let idx = abs(key.hashValue) % palette.count
        return palette[idx]
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

/// Glass card surface.
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

/// Soft pastel orb-blur backdrop behind the window.
struct OrbBackground: View {
    var body: some View {
        ZStack {
            Theme.bg.ignoresSafeArea()
            orb(Theme.lav,  size: 340).offset(x: 150, y: -260)
            orb(Theme.mint, size: 300).offset(x: -160, y: 220)
            orb(Theme.rose, size: 240).offset(x: 120, y: 180)
        }
    }
    private func orb(_ c: Color, size: CGFloat) -> some View {
        Circle()
            .fill(c)
            .frame(width: size, height: size)
            .blur(radius: 90)
            .opacity(0.13)
    }
}

/// Shared currency formatting.
extension Double {
    var asCurrency: String {
        let f = NumberFormatter()
        f.numberStyle = .currency
        f.maximumFractionDigits = 0
        f.currencyCode = "USD"
        return f.string(from: NSNumber(value: self)) ?? "$0"
    }
    var asCurrencyCents: String {
        let f = NumberFormatter()
        f.numberStyle = .currency
        f.currencyCode = "USD"
        return f.string(from: NSNumber(value: self)) ?? "$0.00"
    }
}
