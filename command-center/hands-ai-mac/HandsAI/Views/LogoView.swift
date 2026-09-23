import SwiftUI

/// Hands AI brand mark.
/// Renders the pixel-art PNG from Assets.xcassets/BrandLogo if present,
/// falls back to a vector approximation otherwise.
struct LogoView: View {
    var body: some View {
        GeometryReader { geo in
            let size = min(geo.size.width, geo.size.height)
            ZStack {
                if let _ = NSImage(named: "BrandLogo") {
                    Image("BrandLogo")
                        .resizable()
                        .interpolation(.none)            // keep pixel-art crisp
                        .scaledToFit()
                        .frame(width: size, height: size)
                } else {
                    fallback(size: size)
                }
            }
        }
        .aspectRatio(1, contentMode: .fit)
    }

    private func fallback(size: CGFloat) -> some View {
        ZStack {
            Circle()
                .fill(
                    RadialGradient(
                        colors: [
                            Color(red: 0.55, green: 0.45, blue: 0.95).opacity(0.55),
                            Color(red: 0.25, green: 0.15, blue: 0.55).opacity(0.75),
                            .black.opacity(0.85),
                        ],
                        center: UnitPoint(x: 0.35, y: 0.30),
                        startRadius: 1, endRadius: size * 0.6
                    )
                )
            Image(systemName: "hand.raised.fill")
                .resizable().scaledToFit()
                .frame(width: size * 0.55, height: size * 0.55)
                .foregroundStyle(.white)
            Image(systemName: "laptopcomputer")
                .resizable().scaledToFit()
                .frame(width: size * 0.30, height: size * 0.30)
                .foregroundStyle(.white.opacity(0.92))
                .offset(y: -size * 0.18)
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
    }
}

#Preview {
    LogoView()
        .frame(width: 220, height: 220)
        .padding(40)
        .background(.black)
}
