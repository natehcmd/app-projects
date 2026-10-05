import Foundation
import Security

/// Mac address + token. Address lives in App Group UserDefaults; the token lives
/// in the Keychain (access group = the App Group id, shared with the extension),
/// with an App Group UserDefaults fallback if the Keychain write is refused.
public enum ConnectionStore {
    static let defaults = UserDefaults(suiteName: SaveQueue.groupID) ?? .standard
    static let service = "com.natehoward.agentdrop"

    public static var address: String {
        get { defaults.string(forKey: "mac.address") ?? "" }
        set { defaults.set(newValue.trimmingCharacters(in: .whitespacesAndNewlines), forKey: "mac.address") }
    }

    public static var token: String {
        get { keychainRead() ?? defaults.string(forKey: "mac.token.fallback") ?? "" }
        set {
            let t = newValue.trimmingCharacters(in: .whitespacesAndNewlines)
            if keychainWrite(t) { defaults.removeObject(forKey: "mac.token.fallback") }
            else { defaults.set(t, forKey: "mac.token.fallback") }
        }
    }

    public static var isConfigured: Bool { !address.isEmpty && !token.isEmpty }

    private static func base() -> [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: service,
         kSecAttrAccount as String: "remote-token",
         kSecAttrAccessGroup as String: SaveQueue.groupID]
    }

    private static func keychainRead() -> String? {
        var q = base()
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var out: AnyObject?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess,
              let d = out as? Data else { return nil }
        return String(data: d, encoding: .utf8)
    }

    private static func keychainWrite(_ value: String) -> Bool {
        SecItemDelete(base() as CFDictionary)
        if value.isEmpty { return true }
        var q = base()
        q[kSecValueData as String] = Data(value.utf8)
        q[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        return SecItemAdd(q as CFDictionary, nil) == errSecSuccess
    }
}
