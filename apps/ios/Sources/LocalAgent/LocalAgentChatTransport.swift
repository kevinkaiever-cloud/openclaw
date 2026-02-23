import OpenClawChatUI
import OpenClawKit
import Foundation
import OSLog

final class LocalAgentChatTransport: OpenClawChatTransport, @unchecked Sendable {
    private static let logger = Logger(subsystem: "ai.openclaw.ios", category: "LocalAgentTransport")
    private let config: LocalAgentConfig
    private let sessionStore: LocalAgentSessionStore
    private let agentService: LocalAgentService
    private let eventContinuations = EventContinuationStore()
    private var currentRunTask: Task<Void, Never>?

    init(config: LocalAgentConfig, sessionStore: LocalAgentSessionStore, agentService: LocalAgentService) {
        self.config = config
        self.sessionStore = sessionStore
        self.agentService = agentService
    }

    func requestHistory(sessionKey: String) async throws -> OpenClawChatHistoryPayload {
        let session = await self.sessionStore.session(for: sessionKey)
        let messages = session.messages.map { msg -> AnyCodable in
            AnyCodable([
                "role": msg.role,
                "content": [["type": "text", "text": msg.content]],
                "timestamp": msg.timestamp,
            ] as [String: Any])
        }
        return OpenClawChatHistoryPayload(
            sessionKey: sessionKey,
            sessionId: sessionKey,
            messages: messages,
            thinkingLevel: session.thinkingLevel)
    }

    func sendMessage(
        sessionKey: String,
        message: String,
        thinking: String,
        idempotencyKey: String,
        attachments: [OpenClawChatAttachmentPayload]
    ) async throws -> OpenClawChatSendResponse {
        let runId = idempotencyKey

        let userMessage = LocalAgentStoredMessage(role: "user", content: message)
        await self.sessionStore.appendMessage(userMessage, sessionKey: sessionKey)

        self.currentRunTask = Task { [weak self] in
            guard let self else { return }
            do {
                let session = await self.sessionStore.session(for: sessionKey)
                let history = session.messages.map { AIMessagePart(role: $0.role, content: $0.content) }

                let provider = await MainActor.run { self.config.provider }
                let model = await MainActor.run { self.config.model }
                let apiKey = await MainActor.run { self.config.apiKey(for: provider) }
                let systemPrompt = await MainActor.run { self.config.systemPrompt }
                let maxTokens = await MainActor.run { self.config.maxTokens }
                let customEndpoint = await MainActor.run { self.config.customEndpoint }

                let response = try await self.agentService.sendCompletion(
                    messages: history,
                    systemPrompt: systemPrompt,
                    provider: provider,
                    model: model,
                    apiKey: apiKey,
                    maxTokens: maxTokens,
                    customEndpoint: customEndpoint,
                    streamHandler: { [weak self] text in
                        guard let self else { return }
                        let payload = OpenClawAgentEventPayload(
                            runId: runId,
                            seq: nil,
                            stream: "assistant",
                            ts: Int(Date().timeIntervalSince1970 * 1000),
                            data: ["text": AnyCodable(text)])
                        self.eventContinuations.yield(.agent(payload))
                    })

                let assistantMsg = LocalAgentStoredMessage(role: "assistant", content: response.text)
                await self.sessionStore.appendMessage(assistantMsg, sessionKey: sessionKey)

                let finalPayload = OpenClawChatEventPayload(
                    runId: runId,
                    sessionKey: sessionKey,
                    state: "final",
                    message: nil,
                    errorMessage: nil)
                self.eventContinuations.yield(.chat(finalPayload))
            } catch {
                Self.logger.error("Agent completion failed: \(error.localizedDescription)")
                let errPayload = OpenClawChatEventPayload(
                    runId: runId,
                    sessionKey: sessionKey,
                    state: "error",
                    message: nil,
                    errorMessage: error.localizedDescription)
                self.eventContinuations.yield(.chat(errPayload))
            }
        }

        return OpenClawChatSendResponse(runId: runId, status: "started")
    }

    func abortRun(sessionKey: String, runId: String) async throws {
        self.currentRunTask?.cancel()
        self.currentRunTask = nil
        let abortPayload = OpenClawChatEventPayload(
            runId: runId,
            sessionKey: sessionKey,
            state: "aborted",
            message: nil,
            errorMessage: nil)
        self.eventContinuations.yield(.chat(abortPayload))
    }

    func listSessions(limit: Int?) async throws -> OpenClawChatSessionsListResponse {
        let sessions = await self.sessionStore.listSessions()
        let limited = limit.map { Array(sessions.prefix($0)) } ?? sessions
        let jsonSessions: [[String: Any]] = limited.map { session in
            var entry: [String: Any] = ["key": session.key, "updatedAt": session.updatedAt]
            if let name = session.displayName { entry["displayName"] = name }
            return entry
        }
        let wrapper: [String: Any] = [
            "ts": Date().timeIntervalSince1970 * 1000,
            "count": limited.count,
            "sessions": jsonSessions,
        ]
        let data = try JSONSerialization.data(withJSONObject: wrapper)
        return try JSONDecoder().decode(OpenClawChatSessionsListResponse.self, from: data)
    }

    func requestHealth(timeoutMs: Int) async throws -> Bool {
        let hasKey = await MainActor.run { self.config.hasAPIKey }
        return hasKey
    }

    func events() -> AsyncStream<OpenClawChatTransportEvent> {
        AsyncStream { [weak self] continuation in
            guard let self else {
                continuation.finish()
                return
            }
            let id = self.eventContinuations.add(continuation)
            continuation.onTermination = { [weak self] _ in
                self?.eventContinuations.remove(id)
            }
            // Emit an initial health event.
            Task {
                let hasKey = await MainActor.run { self.config.hasAPIKey }
                continuation.yield(.health(ok: hasKey))
            }
        }
    }

    func setActiveSessionKey(_ sessionKey: String) async throws {
        // No-op for local agent — session switching handled by ChatViewModel re-init.
    }

    func clearSession(_ key: String) async {
        await self.sessionStore.clearSession(key)
    }
}

// Thread-safe store for multiple event stream continuations.
private final class EventContinuationStore: @unchecked Sendable {
    private let lock = NSLock()
    private var nextID: Int = 0
    private var store: [Int: AsyncStream<OpenClawChatTransportEvent>.Continuation] = [:]

    func add(_ continuation: AsyncStream<OpenClawChatTransportEvent>.Continuation) -> Int {
        self.lock.lock()
        defer { self.lock.unlock() }
        let id = self.nextID
        self.nextID += 1
        self.store[id] = continuation
        return id
    }

    func remove(_ id: Int) {
        self.lock.lock()
        defer { self.lock.unlock() }
        self.store.removeValue(forKey: id)
    }

    func yield(_ event: OpenClawChatTransportEvent) {
        self.lock.lock()
        let conts = self.store.values
        self.lock.unlock()
        for cont in conts {
            cont.yield(event)
        }
    }
}
