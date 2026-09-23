import Foundation
import AVFoundation
import Speech
import SwiftUI

/// Ambient triggers: an always-on wake phrase ("hey jarvis") and a double-clap
/// detector, both fed by one microphone tap. Recognition is forced on-device
/// so nothing streams anywhere while idle.
///
/// The service auto-pauses while the main VoiceService is actively listening
/// or speaking (they can't share the input node), and resumes after.
@MainActor
final class WakeService: ObservableObject {
    @AppStorage("wake.enabled") var wakeEnabled: Bool = true {
        didSet { reconcile() }
    }
    @AppStorage("wake.phrase") var wakePhrase: String = "hey jarvis"
    @AppStorage("wake.clapEnabled") var clapEnabled: Bool = true {
        didSet { reconcile() }
    }
    /// What a double clap does: "listen" (arm the mic) or "briefing".
    @AppStorage("wake.clapAction") var clapAction: String = "listen"
    /// Hard mute: kills ambient detection and blocks the hands-free re-arm.
    /// Manual triggers (orb tap, mic button) still work — mute is about the
    /// app never listening on its own.
    @AppStorage("mic.muted") var micMuted: Bool = false {
        didSet { reconcile() }
    }

    @Published private(set) var isAmbient = false

    /// Fired on the wake phrase. Host should ack + start full listening.
    var onWake: (() -> Void)?
    /// Fired on a double clap.
    var onClap: (() -> Void)?

    private let engine = AVAudioEngine()
    private var recognizer: SFSpeechRecognizer?
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var restartTimer: Timer?
    private var suspended = false

    // Clap detection state
    private var lastPeakAt: TimeInterval = 0
    private var firstClapAt: TimeInterval = 0
    private var lastTriggerAt: TimeInterval = 0

    init() {
        recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    }

    // MARK: - Lifecycle

    func start() {
        suspended = false
        reconcile()
    }

    /// Call while the main voice pipeline needs the mic (listening) or while
    /// TTS is playing (so the assistant doesn't wake itself up).
    func suspend() {
        suspended = true
        stopEngine()
    }

    func resume() {
        suspended = false
        reconcile()
    }

    private func reconcile() {
        if suspended || micMuted || (!wakeEnabled && !clapEnabled) {
            stopEngine()
            return
        }
        guard !isAmbient else { return }
        SFSpeechRecognizer.requestAuthorization { [weak self] status in
            Task { @MainActor in
                guard let self else { return }
                // Clap detection works without speech authorization.
                if status != .authorized { self.wakeEnabled = false }
                self.beginAmbient()
            }
        }
    }

    private func beginAmbient() {
        guard !suspended, !micMuted, !isAmbient, wakeEnabled || clapEnabled else { return }

        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        guard format.sampleRate > 0 else { return }

        if wakeEnabled, let recognizer, recognizer.isAvailable {
            request = SFSpeechAudioBufferRecognitionRequest()
            request?.shouldReportPartialResults = true
            if recognizer.supportsOnDeviceRecognition {
                request?.requiresOnDeviceRecognition = true
            }
        }

        input.removeTap(onBus: 0)
        input.installTap(onBus: 0, bufferSize: 2048, format: format) { [weak self] buffer, _ in
            guard let self else { return }
            self.request?.append(buffer)
            if self.clapEnabled { self.scanForClaps(buffer) }
        }

        engine.prepare()
        do { try engine.start() } catch {
            request = nil
            return
        }
        isAmbient = true

        if let request, let recognizer {
            task = recognizer.recognitionTask(with: request) { [weak self] result, error in
                Task { @MainActor in
                    guard let self, self.isAmbient else { return }
                    if let result {
                        let heard = result.bestTranscription.formattedString.lowercased()
                        let phrase = self.wakePhrase
                            .trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
                        if !phrase.isEmpty, heard.contains(phrase) {
                            self.fireWake()
                            return
                        }
                    }
                    // Recognition tasks end after ~1 min or on error — restart.
                    if error != nil || result?.isFinal == true {
                        self.restartAmbientSoon()
                    }
                }
            }
        }

        // Safety net: recycle the recognition task periodically so long idle
        // stretches don't silently kill wake detection.
        restartTimer?.invalidate()
        restartTimer = Timer.scheduledTimer(withTimeInterval: 50, repeats: false) { [weak self] _ in
            Task { @MainActor in self?.restartAmbientSoon() }
        }
    }

    private func restartAmbientSoon() {
        guard isAmbient, !suspended else { return }
        stopEngine()
        Task { @MainActor in
            try? await Task.sleep(nanoseconds: 200_000_000)
            self.reconcile()
        }
    }

    private func stopEngine() {
        restartTimer?.invalidate()
        restartTimer = nil
        task?.cancel()
        task = nil
        request?.endAudio()
        request = nil
        if engine.isRunning { engine.stop() }
        engine.inputNode.removeTap(onBus: 0)
        isAmbient = false
    }

    private func fireWake() {
        stopEngine()
        onWake?()
    }

    // MARK: - Double clap

    /// Two sharp transients 0.12–0.9s apart, with a 2s cooldown after firing.
    private nonisolated static let clapThreshold: Float = 0.35

    private nonisolated func scanForClaps(_ buffer: AVAudioPCMBuffer) {
        guard let data = buffer.floatChannelData?[0] else { return }
        var peak: Float = 0
        for i in 0..<Int(buffer.frameLength) {
            let v = abs(data[i])
            if v > peak { peak = v }
        }
        guard peak >= Self.clapThreshold else { return }
        let now = ProcessInfo.processInfo.systemUptime
        Task { @MainActor in self.registerPeak(at: now) }
    }

    private func registerPeak(at now: TimeInterval) {
        guard now - lastTriggerAt > 2.0 else { return }
        // Debounce the tail of a single clap.
        guard now - lastPeakAt > 0.12 else { lastPeakAt = now; return }
        defer { lastPeakAt = now }

        if firstClapAt > 0, now - firstClapAt < 0.9 {
            firstClapAt = 0
            lastTriggerAt = now
            stopEngine()
            onClap?()
        } else {
            firstClapAt = now
        }
    }
}
