import Carbon.HIToolbox
import AppKit

final class HotkeyService {
    struct Modifiers: OptionSet {
        let rawValue: UInt32
        static let command = Modifiers(rawValue: UInt32(cmdKey))
        static let option  = Modifiers(rawValue: UInt32(optionKey))
        static let shift   = Modifiers(rawValue: UInt32(shiftKey))
        static let control = Modifiers(rawValue: UInt32(controlKey))
    }

    private var eventHandler: EventHandlerRef?
    private var hotKeyRef: EventHotKeyRef?
    private var handler: (() -> Void)?

    func register(keyCode: UInt32, modifiers: Modifiers, handler: @escaping () -> Void) {
        self.handler = handler
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard),
                                 eventKind: UInt32(kEventHotKeyPressed))

        let selfPtr = Unmanaged.passUnretained(self).toOpaque()
        InstallEventHandler(GetApplicationEventTarget(), { _, eventRef, userData in
            guard let userData else { return noErr }
            let svc = Unmanaged<HotkeyService>.fromOpaque(userData).takeUnretainedValue()
            svc.handler?()
            return noErr
        }, 1, &spec, selfPtr, &eventHandler)

        let hotKeyID = EventHotKeyID(signature: OSType(0x48414e44), id: 1) // 'HAND'
        RegisterEventHotKey(keyCode, modifiers.rawValue, hotKeyID,
                            GetApplicationEventTarget(), 0, &hotKeyRef)
    }

    deinit {
        if let h = hotKeyRef { UnregisterEventHotKey(h) }
        if let e = eventHandler { RemoveEventHandler(e) }
    }
}
