import Foundation
import Security

enum LocalAgentProvider: String, CaseIterable, Codable {
    case anthropic = "anthropic"
    case openai = "openai"

    var displayName: String {
        switch self {
        case .anthropic: "Anthropic (Claude)"
        case .openai: "OpenAI (GPT)"
        }
    }

    var defaultModel: String {
        switch self {
        case .anthropic: "claude-sonnet-4-20250514"
        case .openai: "gpt-4o"
        }
    }

    var availableModels: [String] {
        switch self {
        case .anthropic:
            ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-haiku-20240307"]
        case .openai:
            ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1-mini"]
        }
    }
}

@MainActor
final class LocalAgentConfig {
    static let shared = LocalAgentConfig()

    private static let keychainServicePrefix = "ai.openclaw.ios.localagent"
    private static let providerKey = "localAgent.provider"
    private static let modelKey = "localAgent.model"
    private static let enabledKey = "localAgent.enabled"
    private static let systemPromptKey = "localAgent.systemPrompt"
    private static let maxTokensKey = "localAgent.maxTokens"
    private static let customEndpointKey = "localAgent.customEndpoint"

    var isEnabled: Bool {
        get { UserDefaults.standard.bool(forKey: Self.enabledKey) }
        set { UserDefaults.standard.set(newValue, forKey: Self.enabledKey) }
    }

    var provider: LocalAgentProvider {
        get {
            let raw = UserDefaults.standard.string(forKey: Self.providerKey) ?? ""
            return LocalAgentProvider(rawValue: raw) ?? .anthropic
        }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: Self.providerKey) }
    }

    var model: String {
        get {
            let stored = UserDefaults.standard.string(forKey: Self.modelKey) ?? ""
            return stored.isEmpty ? self.provider.defaultModel : stored
        }
        set { UserDefaults.standard.set(newValue, forKey: Self.modelKey) }
    }

    var systemPrompt: String {
        get {
            UserDefaults.standard.string(forKey: Self.systemPromptKey)
                ?? "You are a helpful AI assistant running locally on a mobile device. Be concise and helpful."
        }
        set { UserDefaults.standard.set(newValue, forKey: Self.systemPromptKey) }
    }

    var maxTokens: Int {
        get {
            let stored = UserDefaults.standard.integer(forKey: Self.maxTokensKey)
            return stored > 0 ? stored : 4096
        }
        set { UserDefaults.standard.set(newValue, forKey: Self.maxTokensKey) }
    }

    var customEndpoint: String {
        get { UserDefaults.standard.string(forKey: Self.customEndpointKey) ?? "" }
        set { UserDefaults.standard.set(newValue, forKey: Self.customEndpointKey) }
    }

    var hasAPIKey: Bool {
        let key = self.apiKey(for: self.provider)
        return !key.isEmpty
    }

    func apiKey(for provider: LocalAgentProvider) -> String {
        Self.readKeychain(account: "apiKey.\(provider.rawValue)") ?? ""
    }

    func setAPIKey(_ key: String, for provider: LocalAgentProvider) {
        if key.isEmpty {
            Self.deleteKeychain(account: "apiKey.\(provider.rawValue)")
        } else {
            Self.writeKeychain(account: "apiKey.\(provider.rawValue)", value: key)
        }
    }

    // MARK: - Keychain helpers

    private static func writeKeychain(account: String, value: String) {
        guard let data = value.data(using: .utf8) else { return }
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainServicePrefix,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
        var add = query
        add[kSecValueData as String] = data
        add[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        SecItemAdd(add as CFDictionary, nil)
    }

    private static func readKeychain(account: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainServicePrefix,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    private static func deleteKeychain(account: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainServicePrefix,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
    }
}
