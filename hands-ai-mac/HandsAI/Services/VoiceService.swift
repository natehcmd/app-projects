import Foundation
import AVFoundation
import Speech
import SwiftUI

@MainActor
final class VoiceService: NSObject, ObservableObject {
    @Published var voiceEnabled: Bool = true
    @Published var isSpeaking: Bool = false
    @Published var isListening: Bool = false
    @Published var lastTranscript: String = ""
    @Published var selectedVoiceID: String = ""
    @Published var bestQualityAvailable: AVSpeechSynthesisVoiceQuality = .default

    private let synth = AVSpeechSynthesizer()
    private let audioEngine = AVAudioEngine()
    private var recognizer: SFSpeechRecognizer?
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?

    var onFinalTranscript: ((String) -> Void)?

    override init() {
        super.init()
        synth.delegate = self
        if let best = Self.pickBestVoice() {
            selectedVoiceID = best.identifier
            bestQualityAvailable = best.quality
        }
        recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    }

    // MARK: - Voice picking

    /// Preference: premium en-GB → enhanced en-GB → premium en-US → enhanced en-US →
    /// any en-GB → any en-US → system default. Never picks the low-quality default
    /// (Samantha/Alex) if a better voice exists.
    static func pickBestVoice() -> AVSpeechSynthesisVoice? {
        let voices = AVSpeechSynthesisVoice.speechVoices()
        let prefs: [(prefix: String, quality: AVSpeechSynthesisVoiceQuality?)] = [
            ("en-GB", .premium), ("en-GB", .enhanced),
            ("en-US", .premium), ("en-US", .enhanced),
            ("en-AU", .premium), ("en-AU", .enhanced),
            ("en-IE", .premium), ("en-IE", .enhanced),
            ("en-GB", nil), ("en-US", nil),
        ]
        for p in prefs {
            if let q = p.quality {
                if let v = voices.first(where: { $0.language.hasPrefix(p.prefix) && $0.quality == q }) {
                    return v
                }
            } else {
                if let v = voices.first(where: { $0.language.hasPrefix(p.prefix) }) { return v }
            }
        }
        return AVSpeechSynthesisVoice(language: AVSpeechSynthesisVoice.currentLanguageCode())
    }

    var availableVoices: [AVSpeechSynthesisVoice] {
        AVSpeechSynthesisVoice.speechVoices()
            .filter { $0.language.hasPrefix("en") }
            .sorted { ($0.quality.rawValue, $0.name) > ($1.quality.rawValue, $1.name) }
    }

    /// True if the user has no premium or enhanced English voice installed.
    /// Prompts them to download one in Settings.
    var hasOnlyDefaultVoices: Bool {
        !availableVoices.contains(where: { $0.quality == .premium || $0.quality == .enhanced })
    }

    // MARK: - TTS

    func speak(_ rawText: String) {
        guard voiceEnabled else { return }
        let cleaned = Self.sanitizeForSpeech(rawText)
        let text = Self.trimToSpokenLength(cleaned)
        guard !text.isEmpty else { return }

        synth.stopSpeaking(at: .immediate)

        let chosen: AVSpeechSynthesisVoice?
        if !selectedVoiceID.isEmpty, let v = AVSpeechSynthesisVoice(identifier: selectedVoiceID) {
            chosen = v
        } else {
            chosen = Self.pickBestVoice()
        }

        // Speak sentence-by-sentence: each utterance gets its own prosody and
        // a small pause between them, which sounds far more natural than one
        // run-on utterance.
        for sentence in Self.splitSentences(text) {
            let utter = AVSpeechUtterance(string: sentence)
            utter.voice = chosen
            // Normal conversational pace. Don't slow down — users perceive it as broken.
            utter.rate = AVSpeechUtteranceDefaultSpeechRate
            utter.pitchMultiplier = 1.0
            utter.preUtteranceDelay = 0
            utter.postUtteranceDelay = 0.12
            utter.volume = 1.0
            synth.speak(utter) // queued — AVSpeechSynthesizer plays in order
        }
    }

    static func splitSentences(_ text: String) -> [String] {
        let terminators: Set<Character> = [".", "!", "?"]
        var sentences: [String] = []
        var current = ""
        for ch in text {
            current.append(ch)
            if terminators.contains(ch) {
                let t = current.trimmingCharacters(in: .whitespaces)
                if !t.isEmpty { sentences.append(t) }
                current = ""
            }
        }
        let leftover = current.trimmingCharacters(in: .whitespaces)
        if !leftover.isEmpty { sentences.append(leftover) }
        return sentences.isEmpty ? [text] : sentences
    }

    func stopSpeaking() {
        synth.stopSpeaking(at: .immediate)
        isSpeaking = false
    }

    // MARK: - Speech sanitization

    /// Speak only the first 1–3 sentences (≤240 chars). Longer replies stay visible
    /// in the panel but don't take a minute to read aloud.
    static func trimToSpokenLength(_ input: String) -> String {
        let s = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !s.isEmpty else { return "" }
        // Split on sentence boundaries.
        let terminators: Set<Character> = [".", "!", "?"]
        var sentences: [String] = []
        var current = ""
        for ch in s {
            current.append(ch)
            if terminators.contains(ch) {
                let trimmed = current.trimmingCharacters(in: .whitespaces)
                if !trimmed.isEmpty { sentences.append(trimmed) }
                current = ""
            }
        }
        let leftover = current.trimmingCharacters(in: .whitespaces)
        if !leftover.isEmpty { sentences.append(leftover) }

        var out = ""
        for sentence in sentences.prefix(3) {
            let candidate = out.isEmpty ? sentence : out + " " + sentence
            if candidate.count > 240 { break }
            out = candidate
        }
        return out.isEmpty ? String(s.prefix(240)) : out
    }

    /// Strip markdown, code blocks, JSON-ish blobs, URLs, and other non-spoken
    /// junk before sending to TTS. Code gets summarized rather than read literally.
    static func sanitizeForSpeech(_ input: String) -> String {
        var s = input

        // Fenced code blocks ```lang\n...\n``` → spoken summary
        let fenceRange = NSRange(s.startIndex..<s.endIndex, in: s)
        let fenceRegex = try? NSRegularExpression(pattern: "```[\\s\\S]*?```", options: [])
        if let fenceRegex {
            let matches = fenceRegex.matches(in: s, range: fenceRange)
            if !matches.isEmpty {
                s = fenceRegex.stringByReplacingMatches(
                    in: s, range: NSRange(s.startIndex..<s.endIndex, in: s),
                    withTemplate: " (code block omitted) "
                )
            }
        }

        // Inline `code`
        s = s.replacing(/`([^`]+)`/, with: { $0.output.1 })

        // Markdown links [text](url) → text
        s = s.replacing(/\[([^\]]+)\]\([^)]+\)/, with: { $0.output.1 })

        // Bare URLs → "a link"
        s = s.replacing(/https?:\/\/\S+/, with: { _ in "a link" })

        // Markdown bold / italic
        s = s.replacing(/\*\*([^*]+)\*\*/, with: { $0.output.1 })
        s = s.replacing(/\*([^*]+)\*/, with: { $0.output.1 })
        s = s.replacing(/__([^_]+)__/, with: { $0.output.1 })
        s = s.replacing(/_([^_]+)_/, with: { $0.output.1 })

        // Headers
        s = s.replacing(/(?m)^#+\s+/, with: { _ in "" })

        // List markers
        s = s.replacing(/(?m)^\s*[-*•·]\s+/, with: { _ in "" })
        s = s.replacing(/(?m)^\s*\d+\.\s+/, with: { _ in "" })

        // XML/HTML tags
        s = s.replacing(/<[^>]+>/, with: { _ in "" })

        // Stray brackets / braces likely from JSON
        if Self.looksLikeJSON(s) {
            return "I've prepared structured output for you, sir."
        }

        // Collapse repeated whitespace
        s = s.replacing(/\s+/, with: { _ in " " })

        return s.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private static func looksLikeJSON(_ s: String) -> Bool {
        let trimmed = s.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmed.count > 20 else { return false }
        let opensWithStructure = trimmed.first == "{" || trimmed.first == "["
        let bracePairs = trimmed.filter { $0 == "{" || $0 == "}" }.count
        let bracketPairs = trimmed.filter { $0 == "[" || $0 == "]" }.count
        return opensWithStructure && (bracePairs >= 4 || bracketPairs >= 4)
    }

    // MARK: - STT

    func toggleListening() {
        if isListening { stopListening() } else { startListening() }
    }

    func startListening() {
        guard !isListening else { return }
        SFSpeechRecognizer.requestAuthorization { [weak self] status in
            guard status == .authorized else { return }
            DispatchQueue.main.async { self?.beginRecognition() }
        }
    }

    private func beginRecognition() {
        guard let recognizer, recognizer.isAvailable else { return }
        if audioEngine.isRunning { audioEngine.stop() }

        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        recognitionRequest?.shouldReportPartialResults = true

        let input = audioEngine.inputNode
        let format = input.outputFormat(forBus: 0)
        guard format.sampleRate > 0 else {
            // No input device or permission denied — bail without touching the engine.
            recognitionRequest = nil
            return
        }
        input.removeTap(onBus: 0)
        input.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
            guard buffer.frameLength > 0 else { return }
            self?.recognitionRequest?.append(buffer)
        }

        audioEngine.prepare()
        do {
            try audioEngine.start()
        } catch {
            recognitionRequest = nil
            return
        }
        isListening = true

        recognitionTask = recognizer.recognitionTask(with: recognitionRequest!) { [weak self] result, error in
            guard let self else { return }
            if let result {
                self.lastTranscript = result.bestTranscription.formattedString
                if result.isFinal {
                    let final = self.lastTranscript
                    self.stopListening()
                    self.onFinalTranscript?(final)
                }
            }
            if error != nil { self.stopListening() }
        }
    }

    func stopListening() {
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        recognitionRequest = nil
        recognitionTask = nil
        isListening = false
    }
}

extension VoiceService: AVSpeechSynthesizerDelegate {
    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer,
                                       didStart utterance: AVSpeechUtterance) {
        Task { @MainActor in self.isSpeaking = true }
    }
    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer,
                                       didFinish utterance: AVSpeechUtterance) {
        Task { @MainActor in self.isSpeaking = false }
    }
    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer,
                                       didCancel utterance: AVSpeechUtterance) {
        Task { @MainActor in self.isSpeaking = false }
    }
}

extension AVSpeechSynthesisVoiceQuality {
    var label: String {
        switch self {
        case .premium:  return "Premium"
        case .enhanced: return "Enhanced"
        default:        return "Default"
        }
    }
}
