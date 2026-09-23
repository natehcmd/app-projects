import SwiftUI

@main
struct HandsAIMobileApp: App {
    @StateObject private var remote = RemoteAgentClient()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(remote)
                .preferredColorScheme(.dark)
        }
    }
}

private struct RootView: View {
    @EnvironmentObject var remote: RemoteAgentClient

    var body: some View {
        Group {
            if remote.isConfigured {
                MobileChatView()
            } else {
                ConnectionSettingsView()
            }
        }
        .background(Theme.bg.ignoresSafeArea())
    }
}
