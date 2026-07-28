// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "FileGraph",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(name: "FileGraph", path: "Sources/FileGraph")
    ]
)
