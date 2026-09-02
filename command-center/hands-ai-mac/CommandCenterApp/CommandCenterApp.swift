import SwiftUI

@main
struct CommandCenterApp: App {
    var body: some Scene {
        WindowGroup {
            RootView()
                .frame(minWidth: 900, minHeight: 600)
        }
        .windowStyle(.hiddenTitleBar)
        .windowToolbarStyle(.unified)
        .commands {
            CommandGroup(after: .toolbar) {
                Button("Reload") {
                    NotificationCenter.default.post(name: .commandCenterReload, object: nil)
                }
                .keyboardShortcut("r", modifiers: .command)
            }
        }
    }
}

private struct RootView: View {
    @State private var ready = false

    var body: some View {
        ZStack {
            Theme.bg.ignoresSafeArea()
            if ready {
                CommandCenterWebView(url: CommandCenterLauncher.url)
            } else {
                VStack(spacing: 12) {
                    ProgressView()
                    Text("Starting Command Center…")
                        .font(.system(size: 12, design: .rounded))
                        .foregroundStyle(Theme.inkDim)
                }
            }
        }
        .task {
            await CommandCenterLauncher.ensureRunning()
            ready = true
        }
    }
}
