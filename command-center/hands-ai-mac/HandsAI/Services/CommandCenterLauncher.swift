import Foundation
import AppKit

/// Makes clicking the menu bar icon feel like "opening Command Center" —
/// starts mission-control's server if it isn't already running, then opens
/// the dashboard in the default browser. The two projects stay separate
/// codebases (native Swift agent vs. Python/JS dashboard); this is what makes
/// them feel like one app from the outside.
enum CommandCenterLauncher {
    static let url = URL(string: "http://127.0.0.1:8450")!
    private static let statusURL = URL(string: "http://127.0.0.1:8450/api/status")!

    /// Sibling folder to this app's own repo location, per the command-center
    /// restructure. If this Mac is ever set up differently, starting the
    /// server just silently no-ops — opening the browser still happens, it'll
    /// just show a connection error instead of crashing anything.
    private static let missionControlDir = URL(fileURLWithPath: NSHomeDirectory())
        .appendingPathComponent("Projects/app-projects/command-center/mission-control")

    @MainActor
    static func open() {
        Task {
            await ensureRunning()
            NSWorkspace.shared.open(url)
        }
    }

    /// Starts the server if it isn't already up. Shared by `open()` (opens
    /// the system browser) and the native CommandCenterApp target (loads the
    /// same URL into its own in-app WebView instead).
    @MainActor
    static func ensureRunning() async {
        let running = await isRunning()
        if !running {
            startServer()
            // Give uvicorn a moment to bind before anything tries to load it.
            try? await Task.sleep(nanoseconds: 1_500_000_000)
        }
    }

    private static func isRunning() async -> Bool {
        var request = URLRequest(url: statusURL)
        request.timeoutInterval = 1.5
        guard let (_, response) = try? await URLSession.shared.data(for: request),
              let http = response as? HTTPURLResponse else { return false }
        return http.statusCode == 200
    }

    private static func startServer() {
        let uvicorn = missionControlDir.appendingPathComponent(".venv/bin/uvicorn")
        guard FileManager.default.isExecutableFile(atPath: uvicorn.path) else { return }

        let process = Process()
        process.executableURL = uvicorn
        process.arguments = ["server:app", "--host", "127.0.0.1", "--port", "8450"]
        process.currentDirectoryURL = missionControlDir

        // Detached — outlives this app; mission-control is meant to keep
        // running as its own background service, not tied to Hands AI's
        // lifecycle. Log to the same place its own launchd setup would.
        let logURL = missionControlDir.appendingPathComponent("data/server.log")
        try? FileManager.default.createDirectory(at: logURL.deletingLastPathComponent(),
                                                 withIntermediateDirectories: true)
        if !FileManager.default.fileExists(atPath: logURL.path) {
            FileManager.default.createFile(atPath: logURL.path, contents: nil)
        }
        if let handle = try? FileHandle(forWritingTo: logURL) {
            handle.seekToEndOfFile()
            process.standardOutput = handle
            process.standardError = handle
        }
        try? process.run()
    }
}
