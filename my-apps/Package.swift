// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "MyApps",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(name: "MyApps", path: "Sources/MyApps")
    ]
)
