import SwiftUI

@main
struct HandsAIApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        Settings {
            SettingsView()
                .environmentObject(appDelegate.ollama)
                .environmentObject(appDelegate.claude)
                .environmentObject(appDelegate.voice)
                .environmentObject(appDelegate.profiles)
                .environmentObject(appDelegate.skills)
        }
    }
}
