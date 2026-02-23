import OpenClawChatUI
import OpenClawKit
import SwiftUI

struct ChatSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var viewModel: OpenClawChatViewModel
    private let userAccent: Color?
    private let agentName: String?
    private let isLocalAgent: Bool

    init(gateway: GatewayNodeSession, sessionKey: String, agentName: String? = nil, userAccent: Color? = nil) {
        let transport = IOSGatewayChatTransport(gateway: gateway)
        self._viewModel = State(
            initialValue: OpenClawChatViewModel(
                sessionKey: sessionKey,
                transport: transport))
        self.userAccent = userAccent
        self.agentName = agentName
        self.isLocalAgent = false
    }

    init(localTransport: LocalAgentChatTransport, sessionKey: String, agentName: String? = nil, userAccent: Color? = nil) {
        self._viewModel = State(
            initialValue: OpenClawChatViewModel(
                sessionKey: sessionKey,
                transport: localTransport))
        self.userAccent = userAccent
        self.agentName = agentName
        self.isLocalAgent = true
    }

    var body: some View {
        NavigationStack {
            OpenClawChatView(
                viewModel: self.viewModel,
                showsSessionSwitcher: true,
                userAccent: self.userAccent)
                .navigationTitle(self.chatTitle)
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            self.dismiss()
                        } label: {
                            Image(systemName: "xmark")
                        }
                        .accessibilityLabel("Close")
                    }
                }
        }
    }

    private var chatTitle: String {
        let trimmed = (self.agentName ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            return self.isLocalAgent ? "Local Agent" : "Chat"
        }
        return self.isLocalAgent ? "Local: \(trimmed)" : "Chat (\(trimmed))"
    }
}
