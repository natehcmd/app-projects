import Foundation
import SwiftUI

/// A persona the agent can run as. Profiles change the system-prompt persona,
/// the preferred model, and the sampling temperature — tools stay shared.
struct Profile: Identifiable, Codable, Equatable {
    var id = UUID()
    var name: String
    var icon: String          // SF Symbol
    var tagline: String
    var persona: String       // injected into the system prompt
    var model: String         // "" = auto (use the global picker's model)
    var temperature: Double
    var builtIn: Bool = false
}

extension Profile {
    static let defaults: [Profile] = [
        Profile(
            name: "Jarvis",
            icon: "sparkles",
            tagline: "The default butler — calm, capable, dry wit.",
            persona: """
            Calm, capable, dry wit. British-butler tone without laying it on thick. \
            Address the user as "sir" occasionally, not every sentence. Never sycophantic \
            ("great question!" is banned). Never ask the user to help you improve.
            """,
            model: "",
            temperature: 0.4,
            builtIn: true
        ),
        Profile(
            name: "Coder",
            icon: "chevron.left.forwardslash.chevron.right",
            tagline: "Terse engineering copilot — files, git, builds.",
            persona: """
            You are in engineering mode. Be terse and precise — no butler flourishes. \
            Prefer tools over talk: read the file, run the command, report the result. \
            When asked about code, quote exact paths and line references. Assume the \
            user is an experienced developer.
            """,
            model: "",
            temperature: 0.2,
            builtIn: true
        ),
        Profile(
            name: "Researcher",
            icon: "text.magnifyingglass",
            tagline: "Web-first — searches, fetches, summarizes with sources.",
            persona: """
            You are in research mode. For anything factual or current, use web_search \
            and web_fetch before answering — do not rely on training memory for news, \
            prices, or versions. Summarize findings in plain language and mention the \
            source site by name.
            """,
            model: "",
            temperature: 0.5,
            builtIn: true
        ),
        Profile(
            name: "Operator",
            icon: "macwindow.on.rectangle",
            tagline: "Mac control — apps, AppleScript, automations.",
            persona: """
            You are in operator mode: the user's hands on this Mac. Prefer acting over \
            explaining — open the app, run the AppleScript, set the clipboard, send the \
            notification. Confirm only before destructive or irreversible actions. \
            Report what you did in one short sentence.
            """,
            model: "",
            temperature: 0.3,
            builtIn: true
        ),
    ]
}

@MainActor
final class ProfileStore: ObservableObject {
    @Published var profiles: [Profile] = []
    @Published var selectedID: UUID? {
        didSet { UserDefaults.standard.set(selectedID?.uuidString, forKey: "profile.selected") }
    }

    var selected: Profile {
        profiles.first(where: { $0.id == selectedID }) ?? profiles.first ?? Profile.defaults[0]
    }

    private var fileURL: URL {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("HandsAI", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("profiles.json")
    }

    init() {
        load()
    }

    func load() {
        if let data = try? Data(contentsOf: fileURL),
           let saved = try? JSONDecoder().decode([Profile].self, from: data),
           !saved.isEmpty {
            profiles = saved
        } else {
            profiles = Profile.defaults
            save()
        }
        if let raw = UserDefaults.standard.string(forKey: "profile.selected"),
           let id = UUID(uuidString: raw),
           profiles.contains(where: { $0.id == id }) {
            selectedID = id
        } else {
            selectedID = profiles.first?.id
        }
    }

    func save() {
        if let data = try? JSONEncoder().encode(profiles) {
            try? data.write(to: fileURL, options: .atomic)
        }
    }

    func select(_ profile: Profile) {
        selectedID = profile.id
    }

    func update(_ profile: Profile) {
        if let i = profiles.firstIndex(where: { $0.id == profile.id }) {
            profiles[i] = profile
            save()
        }
    }

    func addProfile() -> Profile {
        let p = Profile(name: "New Profile", icon: "person.crop.circle",
                        tagline: "Custom persona.",
                        persona: "Describe how this persona should behave.",
                        model: "", temperature: 0.4)
        profiles.append(p)
        save()
        return p
    }

    func delete(_ profile: Profile) {
        guard !profile.builtIn else { return }
        profiles.removeAll { $0.id == profile.id }
        if selectedID == profile.id { selectedID = profiles.first?.id }
        save()
    }

    func resetBuiltIns() {
        let custom = profiles.filter { !$0.builtIn }
        profiles = Profile.defaults + custom
        selectedID = profiles.first?.id
        save()
    }
}
