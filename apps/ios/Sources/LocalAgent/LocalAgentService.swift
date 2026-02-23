import Foundation
import OSLog

struct AIMessagePart {
    let role: String
    let content: String
}

struct AICompletionResponse {
    let text: String
    let stopReason: String?
    let inputTokens: Int?
    let outputTokens: Int?
}

enum LocalAgentError: LocalizedError {
    case noAPIKey
    case invalidResponse(String)
    case apiError(Int, String)
    case networkError(String)

    var errorDescription: String? {
        switch self {
        case .noAPIKey:
            "No API key configured. Please set your API key in Settings."
        case .invalidResponse(let msg):
            "Invalid response: \(msg)"
        case .apiError(let code, let msg):
            "API error (\(code)): \(msg)"
        case .networkError(let msg):
            "Network error: \(msg)"
        }
    }
}

actor LocalAgentService {
    private static let logger = Logger(subsystem: "ai.openclaw.ios", category: "LocalAgent")

    func sendCompletion(
        messages: [AIMessagePart],
        systemPrompt: String,
        provider: LocalAgentProvider,
        model: String,
        apiKey: String,
        maxTokens: Int,
        customEndpoint: String,
        streamHandler: @Sendable @escaping (String) -> Void
    ) async throws -> AICompletionResponse {
        guard !apiKey.isEmpty else { throw LocalAgentError.noAPIKey }

        switch provider {
        case .anthropic:
            return try await self.callAnthropic(
                messages: messages,
                systemPrompt: systemPrompt,
                model: model,
                apiKey: apiKey,
                maxTokens: maxTokens,
                customEndpoint: customEndpoint,
                streamHandler: streamHandler)
        case .openai:
            return try await self.callOpenAI(
                messages: messages,
                systemPrompt: systemPrompt,
                model: model,
                apiKey: apiKey,
                maxTokens: maxTokens,
                customEndpoint: customEndpoint,
                streamHandler: streamHandler)
        }
    }

    // MARK: - Anthropic API

    private func callAnthropic(
        messages: [AIMessagePart],
        systemPrompt: String,
        model: String,
        apiKey: String,
        maxTokens: Int,
        customEndpoint: String,
        streamHandler: @Sendable @escaping (String) -> Void
    ) async throws -> AICompletionResponse {
        let baseURL = customEndpoint.isEmpty ? "https://api.anthropic.com" : customEndpoint
        let url = URL(string: "\(baseURL)/v1/messages")!

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(apiKey, forHTTPHeaderField: "x-api-key")
        request.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
        request.timeoutInterval = 120

        let msgArray = messages.map { msg -> [String: Any] in
            ["role": msg.role, "content": msg.content]
        }

        let body: [String: Any] = [
            "model": model,
            "max_tokens": maxTokens,
            "system": systemPrompt,
            "messages": msgArray,
            "stream": true,
        ]

        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (bytes, response) = try await URLSession.shared.bytes(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw LocalAgentError.invalidResponse("Not an HTTP response")
        }

        if httpResponse.statusCode != 200 {
            var errorBody = ""
            for try await line in bytes.lines {
                errorBody += line
            }
            throw LocalAgentError.apiError(httpResponse.statusCode, errorBody)
        }

        var fullText = ""
        var stopReason: String?
        var inputTokens: Int?
        var outputTokens: Int?

        for try await line in bytes.lines {
            if Task.isCancelled { break }
            guard line.hasPrefix("data: ") else { continue }
            let jsonStr = String(line.dropFirst(6))
            if jsonStr == "[DONE]" { break }
            guard let data = jsonStr.data(using: .utf8),
                  let event = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            else { continue }

            let eventType = event["type"] as? String
            switch eventType {
            case "content_block_delta":
                if let delta = event["delta"] as? [String: Any],
                   let text = delta["text"] as? String
                {
                    fullText += text
                    streamHandler(fullText)
                }
            case "message_delta":
                if let delta = event["delta"] as? [String: Any] {
                    stopReason = delta["stop_reason"] as? String
                }
                if let usage = event["usage"] as? [String: Any] {
                    outputTokens = usage["output_tokens"] as? Int
                }
            case "message_start":
                if let message = event["message"] as? [String: Any],
                   let usage = message["usage"] as? [String: Any]
                {
                    inputTokens = usage["input_tokens"] as? Int
                }
            default:
                break
            }
        }

        Self.logger.info("Anthropic completion done. tokens in=\(inputTokens ?? 0) out=\(outputTokens ?? 0)")
        return AICompletionResponse(
            text: fullText,
            stopReason: stopReason,
            inputTokens: inputTokens,
            outputTokens: outputTokens)
    }

    // MARK: - OpenAI API

    private func callOpenAI(
        messages: [AIMessagePart],
        systemPrompt: String,
        model: String,
        apiKey: String,
        maxTokens: Int,
        customEndpoint: String,
        streamHandler: @Sendable @escaping (String) -> Void
    ) async throws -> AICompletionResponse {
        let baseURL = customEndpoint.isEmpty ? "https://api.openai.com" : customEndpoint
        let url = URL(string: "\(baseURL)/v1/chat/completions")!

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.timeoutInterval = 120

        var allMessages: [[String: Any]] = [["role": "system", "content": systemPrompt]]
        allMessages += messages.map { ["role": $0.role, "content": $0.content] }

        let body: [String: Any] = [
            "model": model,
            "max_tokens": maxTokens,
            "messages": allMessages,
            "stream": true,
        ]

        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (bytes, response) = try await URLSession.shared.bytes(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw LocalAgentError.invalidResponse("Not an HTTP response")
        }

        if httpResponse.statusCode != 200 {
            var errorBody = ""
            for try await line in bytes.lines {
                errorBody += line
            }
            throw LocalAgentError.apiError(httpResponse.statusCode, errorBody)
        }

        var fullText = ""
        var stopReason: String?
        var inputTokens: Int?
        var outputTokens: Int?

        for try await line in bytes.lines {
            if Task.isCancelled { break }
            guard line.hasPrefix("data: ") else { continue }
            let jsonStr = String(line.dropFirst(6))
            if jsonStr == "[DONE]" { break }
            guard let data = jsonStr.data(using: .utf8),
                  let event = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            else { continue }

            if let choices = event["choices"] as? [[String: Any]],
               let first = choices.first
            {
                if let delta = first["delta"] as? [String: Any],
                   let text = delta["content"] as? String
                {
                    fullText += text
                    streamHandler(fullText)
                }
                if let finish = first["finish_reason"] as? String {
                    stopReason = finish
                }
            }
            if let usage = event["usage"] as? [String: Any] {
                inputTokens = usage["prompt_tokens"] as? Int
                outputTokens = usage["completion_tokens"] as? Int
            }
        }

        Self.logger.info("OpenAI completion done. tokens in=\(inputTokens ?? 0) out=\(outputTokens ?? 0)")
        return AICompletionResponse(
            text: fullText,
            stopReason: stopReason,
            inputTokens: inputTokens,
            outputTokens: outputTokens)
    }
}
