import SwiftUI

struct LocalAgentSettingsView: View {
    @State private var config = LocalAgentConfig.shared
    @State private var apiKeyInput: String = ""
    @State private var showAPIKey: Bool = false
    @State private var selectedProvider: LocalAgentProvider = .anthropic
    @State private var selectedModel: String = ""
    @State private var systemPromptInput: String = ""
    @State private var maxTokensInput: String = ""
    @State private var customEndpointInput: String = ""
    @State private var showAdvanced: Bool = false
    @State private var testStatusText: String?
    @State private var isTesting: Bool = false

    var body: some View {
        Form {
            Section {
                Toggle("Enable Local Agent", isOn: Binding(
                    get: { self.config.isEnabled },
                    set: { self.config.isEnabled = $0 }))

                Text("Run AI agents directly on your device without a Gateway server. Requires an API key from your AI provider.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            } header: {
                Label("Local Agent Mode", systemImage: "cpu")
            }

            Section {
                Picker("Provider", selection: self.$selectedProvider) {
                    ForEach(LocalAgentProvider.allCases, id: \.self) { provider in
                        Text(provider.displayName).tag(provider)
                    }
                }
                .onChange(of: self.selectedProvider) { _, newValue in
                    self.config.provider = newValue
                    self.selectedModel = newValue.defaultModel
                    self.config.model = newValue.defaultModel
                    self.apiKeyInput = self.config.apiKey(for: newValue)
                }

                Picker("Model", selection: self.$selectedModel) {
                    ForEach(self.selectedProvider.availableModels, id: \.self) { model in
                        Text(model).tag(model)
                    }
                }
                .onChange(of: self.selectedModel) { _, newValue in
                    self.config.model = newValue
                }
            } header: {
                Label("AI Provider", systemImage: "brain")
            }

            Section {
                HStack {
                    if self.showAPIKey {
                        TextField("API Key", text: self.$apiKeyInput)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .font(.system(.body, design: .monospaced))
                    } else {
                        SecureField("API Key", text: self.$apiKeyInput)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                    }
                    Button {
                        self.showAPIKey.toggle()
                    } label: {
                        Image(systemName: self.showAPIKey ? "eye.slash" : "eye")
                            .foregroundStyle(.secondary)
                    }
                    .buttonStyle(.plain)
                }
                .onChange(of: self.apiKeyInput) { _, newValue in
                    self.config.setAPIKey(newValue, for: self.selectedProvider)
                }

                if self.selectedProvider == .anthropic {
                    Text("Get your key at [console.anthropic.com](https://console.anthropic.com/settings/keys)")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                } else {
                    Text("Get your key at [platform.openai.com](https://platform.openai.com/api-keys)")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Button {
                    Task { await self.testAPIKey() }
                } label: {
                    HStack {
                        if self.isTesting {
                            ProgressView()
                                .progressViewStyle(.circular)
                                .controlSize(.small)
                            Text("Testing...")
                        } else {
                            Image(systemName: "checkmark.circle")
                            Text("Test Connection")
                        }
                    }
                }
                .disabled(self.apiKeyInput.isEmpty || self.isTesting)

                if let status = self.testStatusText {
                    Text(status)
                        .font(.footnote)
                        .foregroundStyle(status.contains("Success") ? .green : .red)
                }
            } header: {
                Label("API Key", systemImage: "key")
            }

            Section {
                DisclosureGroup("Advanced Settings", isExpanded: self.$showAdvanced) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("System Prompt")
                            .font(.footnote.weight(.medium))
                        TextEditor(text: self.$systemPromptInput)
                            .frame(minHeight: 80)
                            .font(.system(.footnote, design: .monospaced))
                            .overlay(
                                RoundedRectangle(cornerRadius: 6)
                                    .stroke(.tertiary, lineWidth: 0.5))
                    }
                    .onChange(of: self.systemPromptInput) { _, newValue in
                        self.config.systemPrompt = newValue
                    }

                    HStack {
                        Text("Max Tokens")
                        Spacer()
                        TextField("4096", text: self.$maxTokensInput)
                            .keyboardType(.numberPad)
                            .frame(width: 80)
                            .multilineTextAlignment(.trailing)
                    }
                    .onChange(of: self.maxTokensInput) { _, newValue in
                        if let val = Int(newValue), val > 0 {
                            self.config.maxTokens = val
                        }
                    }

                    TextField("Custom API Endpoint (optional)", text: self.$customEndpointInput)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .font(.system(.body, design: .monospaced))
                        .onChange(of: self.customEndpointInput) { _, newValue in
                            self.config.customEndpoint = newValue
                        }

                    Text("Leave blank to use the default endpoint. Use for proxies or self-hosted models.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .navigationTitle("Local Agent")
        .onAppear {
            self.selectedProvider = self.config.provider
            self.selectedModel = self.config.model
            self.apiKeyInput = self.config.apiKey(for: self.config.provider)
            self.systemPromptInput = self.config.systemPrompt
            self.maxTokensInput = String(self.config.maxTokens)
            self.customEndpointInput = self.config.customEndpoint
        }
    }

    private func testAPIKey() async {
        self.isTesting = true
        self.testStatusText = nil
        defer { self.isTesting = false }

        let service = LocalAgentService()
        let messages = [AIMessagePart(role: "user", content: "Say hello in one word.")]
        do {
            let response = try await service.sendCompletion(
                messages: messages,
                systemPrompt: "Respond briefly.",
                provider: self.selectedProvider,
                model: self.selectedModel,
                apiKey: self.apiKeyInput,
                maxTokens: 50,
                customEndpoint: self.customEndpointInput,
                streamHandler: { _ in })
            self.testStatusText = "Success! Response: \(response.text.prefix(50))"
        } catch {
            self.testStatusText = "Failed: \(error.localizedDescription)"
        }
    }
}
