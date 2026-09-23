import Foundation
import SwiftUI

/// The spoken daily briefing: calendar, reminders, weather, and machine health,
/// composed into a few sentences and delivered on the first wake of the day.
///
/// Gathering runs in the background and the text is cached, so when the wake
/// phrase lands the assistant answers instantly instead of making the user
/// wait on four tool calls.
@MainActor
final class BriefingService: ObservableObject {
    @AppStorage("briefing.enabled") var enabled: Bool = true
    /// yyyy-MM-dd of the last briefing spoken, so it happens once a day.
    @AppStorage("briefing.lastSpokenDay") private var lastSpokenDay: String = ""

    @Published private(set) var cached: String = ""
    @Published private(set) var isPreparing = false

    private weak var voice: VoiceService?
    private weak var stats: StatsService?

    func attach(voice: VoiceService, stats: StatsService) {
        self.voice = voice
        self.stats = stats
    }

    static var todayKey: String {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: Date())
    }

    var alreadySpokenToday: Bool { lastSpokenDay == Self.todayKey }

    /// Time-of-day greeting, butler style.
    static func greeting() -> String {
        let hour = Calendar.current.component(.hour, from: Date())
        switch hour {
        case 0..<12:  return "Good morning, sir."
        case 12..<18: return "Good afternoon, sir."
        default:      return "Good evening, sir."
        }
    }

    /// Build the briefing text. Safe to call repeatedly; cheap after the first.
    @discardableResult
    func prepare() async -> String {
        if !cached.isEmpty { return cached }
        isPreparing = true
        defer { isPreparing = false }

        var parts: [String] = [Self.greeting()]

        let events = Tools.calendarToday()
        parts.append(Self.summarizeCalendar(events))

        let reminders = Tools.remindersList()
        if let line = Self.summarizeReminders(reminders) { parts.append(line) }

        let w = await Tools.weather(args: Tools.Args([:]))
        if !w.hasPrefix("error:"), !w.isEmpty {
            parts.append(Self.summarizeWeather(w))
        }

        if let s = stats?.stats, s.cpuPercent > 85 {
            parts.append(String(format: "Your CPU is running hot at %.0f percent.", s.cpuPercent))
        }

        cached = parts.joined(separator: " ")
        return cached
    }

    /// Speak the briefing and mark today as done.
    func speakBriefing() async {
        let text = await prepare()
        lastSpokenDay = Self.todayKey
        voice?.speak(text)
    }

    /// Called on the first wake of the day.
    func speakIfDue() async {
        guard enabled, !alreadySpokenToday else { return }
        await speakBriefing()
    }

    func invalidate() { cached = "" }

    // MARK: - Summarizers
    // Tool output is human-readable text, not JSON — keep these forgiving.

    static func summarizeCalendar(_ raw: String) -> String {
        let lines = raw.split(separator: "\n").map(String.init)
            .filter { !$0.isEmpty && !$0.hasPrefix("error:") }
        guard !lines.isEmpty else { return "Your calendar is clear today." }
        if lines.count == 1 { return "One event today: \(lines[0])." }
        return "You have \(lines.count) events today. First up, \(lines[0])."
    }

    static func summarizeReminders(_ raw: String) -> String? {
        let lines = raw.split(separator: "\n").map(String.init)
            .filter { !$0.isEmpty && !$0.hasPrefix("error:") }
        guard !lines.isEmpty else { return nil }
        if lines.count == 1 { return "One reminder outstanding: \(lines[0])." }
        return "\(lines.count) reminders outstanding."
    }

    static func summarizeWeather(_ raw: String) -> String {
        let first = raw.split(separator: "\n").first.map(String.init) ?? raw
        return "Weather: \(first.trimmingCharacters(in: .whitespaces))."
    }
}
