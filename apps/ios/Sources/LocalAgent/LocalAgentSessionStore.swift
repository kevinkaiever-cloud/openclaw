import Foundation
import OSLog

struct LocalAgentStoredMessage: Codable {
    let id: String
    let role: String
    let content: String
    let timestamp: Double

    init(id: String = UUID().uuidString, role: String, content: String, timestamp: Double = Date().timeIntervalSince1970 * 1000) {
        self.id = id
        self.role = role
        self.content = content
        self.timestamp = timestamp
    }
}

struct LocalAgentSession: Codable {
    let key: String
    var displayName: String?
    var messages: [LocalAgentStoredMessage]
    var thinkingLevel: String
    var updatedAt: Double

    init(key: String, displayName: String? = nil) {
        self.key = key
        self.displayName = displayName
        self.messages = []
        self.thinkingLevel = "off"
        self.updatedAt = Date().timeIntervalSince1970 * 1000
    }
}

actor LocalAgentSessionStore {
    private static let logger = Logger(subsystem: "ai.openclaw.ios", category: "LocalSessionStore")
    private let baseDir: URL
    private var cache: [String: LocalAgentSession] = [:]

    init() {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        self.baseDir = docs.appendingPathComponent("local-agent-sessions", isDirectory: true)
        try? FileManager.default.createDirectory(at: self.baseDir, withIntermediateDirectories: true)
    }

    func session(for key: String) -> LocalAgentSession {
        if let cached = self.cache[key] { return cached }
        let url = self.fileURL(for: key)
        if let data = try? Data(contentsOf: url),
           let session = try? JSONDecoder().decode(LocalAgentSession.self, from: data)
        {
            self.cache[key] = session
            return session
        }
        let fresh = LocalAgentSession(key: key)
        self.cache[key] = fresh
        return fresh
    }

    func appendMessage(_ message: LocalAgentStoredMessage, sessionKey: String) {
        var session = self.session(for: sessionKey)
        session.messages.append(message)
        session.updatedAt = Date().timeIntervalSince1970 * 1000
        self.cache[sessionKey] = session
        self.persist(session)
    }

    func setThinkingLevel(_ level: String, sessionKey: String) {
        var session = self.session(for: sessionKey)
        session.thinkingLevel = level
        self.cache[sessionKey] = session
        self.persist(session)
    }

    func clearSession(_ key: String) {
        var session = self.session(for: key)
        session.messages = []
        session.updatedAt = Date().timeIntervalSince1970 * 1000
        self.cache[key] = session
        self.persist(session)
    }

    func listSessions() -> [LocalAgentSession] {
        let fm = FileManager.default
        guard let contents = try? fm.contentsOfDirectory(at: self.baseDir, includingPropertiesForKeys: nil) else {
            return []
        }
        var sessions: [LocalAgentSession] = []
        for url in contents where url.pathExtension == "json" {
            if let data = try? Data(contentsOf: url),
               let session = try? JSONDecoder().decode(LocalAgentSession.self, from: data)
            {
                sessions.append(session)
                self.cache[session.key] = session
            }
        }
        return sessions.sorted { ($0.updatedAt) > ($1.updatedAt) }
    }

    private func persist(_ session: LocalAgentSession) {
        do {
            let data = try JSONEncoder().encode(session)
            try data.write(to: self.fileURL(for: session.key), options: .atomic)
        } catch {
            Self.logger.error("Failed to persist session \(session.key): \(error.localizedDescription)")
        }
    }

    private func fileURL(for key: String) -> URL {
        let safe = key.replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: ":", with: "_")
        return self.baseDir.appendingPathComponent("\(safe).json")
    }
}
