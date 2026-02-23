package ai.openclaw.android.agent

import ai.openclaw.android.chat.ChatMessage
import ai.openclaw.android.chat.ChatMessageContent
import ai.openclaw.android.chat.ChatPendingToolCall
import ai.openclaw.android.chat.ChatSessionEntry
import ai.openclaw.android.chat.OutgoingAttachment
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

class LocalChatController(
  private val scope: CoroutineScope,
  private val config: LocalAgentConfig,
  private val sessionStore: LocalSessionStore,
  private val agentService: LocalAgentService,
) {
  private val _sessionKey = MutableStateFlow("local-main")
  val sessionKey: StateFlow<String> = _sessionKey.asStateFlow()

  private val _sessionId = MutableStateFlow<String?>(null)
  val sessionId: StateFlow<String?> = _sessionId.asStateFlow()

  private val _messages = MutableStateFlow<List<ChatMessage>>(emptyList())
  val messages: StateFlow<List<ChatMessage>> = _messages.asStateFlow()

  private val _errorText = MutableStateFlow<String?>(null)
  val errorText: StateFlow<String?> = _errorText.asStateFlow()

  private val _healthOk = MutableStateFlow(false)
  val healthOk: StateFlow<Boolean> = _healthOk.asStateFlow()

  private val _thinkingLevel = MutableStateFlow("off")
  val thinkingLevel: StateFlow<String> = _thinkingLevel.asStateFlow()

  private val _pendingRunCount = MutableStateFlow(0)
  val pendingRunCount: StateFlow<Int> = _pendingRunCount.asStateFlow()

  private val _streamingAssistantText = MutableStateFlow<String?>(null)
  val streamingAssistantText: StateFlow<String?> = _streamingAssistantText.asStateFlow()

  private val _pendingToolCalls = MutableStateFlow<List<ChatPendingToolCall>>(emptyList())
  val pendingToolCalls: StateFlow<List<ChatPendingToolCall>> = _pendingToolCalls.asStateFlow()

  private val _sessions = MutableStateFlow<List<ChatSessionEntry>>(emptyList())
  val sessions: StateFlow<List<ChatSessionEntry>> = _sessions.asStateFlow()

  private val pendingRuns = mutableSetOf<String>()
  private val pendingRunTimeoutJobs = ConcurrentHashMap<String, Job>()
  private val pendingRunTimeoutMs = 120_000L

  private var currentRunJob: Job? = null

  fun load(sessionKey: String) {
    val key = sessionKey.trim().ifEmpty { "local-main" }
    _sessionKey.value = key
    scope.launch { bootstrap() }
  }

  fun refresh() {
    scope.launch { bootstrap() }
  }

  fun refreshSessions(limit: Int? = null) {
    scope.launch {
      val stored = sessionStore.listSessions()
      val limited = if (limit != null) stored.take(limit) else stored
      _sessions.value = limited.map { s ->
        ChatSessionEntry(
          key = s.key,
          updatedAtMs = s.updatedAt.toLong(),
          displayName = s.displayName,
        )
      }
    }
  }

  fun setThinkingLevel(level: String) {
    val normalized = normalizeThinking(level)
    if (normalized == _thinkingLevel.value) return
    _thinkingLevel.value = normalized
    sessionStore.setThinkingLevel(normalized, _sessionKey.value)
  }

  fun switchSession(sessionKey: String) {
    val key = sessionKey.trim()
    if (key.isEmpty() || key == _sessionKey.value) return
    _sessionKey.value = key
    scope.launch { bootstrap() }
  }

  @Suppress("UNUSED_PARAMETER")
  fun sendMessage(
    message: String,
    thinkingLevel: String,
    attachments: List<OutgoingAttachment>,
  ) {
    val trimmed = message.trim()
    if (trimmed.isEmpty() && attachments.isEmpty()) return

    val runId = UUID.randomUUID().toString()
    val text = if (trimmed.isEmpty() && attachments.isNotEmpty()) "See attached." else trimmed
    val key = _sessionKey.value

    val userMsg = StoredMessage(role = "user", content = text)
    sessionStore.appendMessage(userMsg, key)

    _messages.value = _messages.value + ChatMessage(
      id = UUID.randomUUID().toString(),
      role = "user",
      content = listOf(ChatMessageContent(type = "text", text = text)),
      timestampMs = System.currentTimeMillis(),
    )

    armPendingRunTimeout(runId)
    synchronized(pendingRuns) {
      pendingRuns.add(runId)
      _pendingRunCount.value = pendingRuns.size
    }

    _errorText.value = null
    _streamingAssistantText.value = null

    currentRunJob = scope.launch {
      try {
        val session = sessionStore.getSession(key)
        val response = agentService.sendCompletion(
          messages = session.messages,
          systemPrompt = config.systemPrompt,
          provider = config.provider,
          model = config.model,
          apiKey = config.getApiKey(config.provider),
          maxTokens = config.maxTokens,
          customEndpoint = config.customEndpoint,
          onStream = { fullText ->
            _streamingAssistantText.value = fullText
          },
        )

        val assistantMsg = StoredMessage(role = "assistant", content = response.text)
        sessionStore.appendMessage(assistantMsg, key)

        _messages.value = _messages.value + ChatMessage(
          id = UUID.randomUUID().toString(),
          role = "assistant",
          content = listOf(ChatMessageContent(type = "text", text = response.text)),
          timestampMs = System.currentTimeMillis(),
        )

        clearPendingRun(runId)
        _streamingAssistantText.value = null
      } catch (err: Throwable) {
        clearPendingRun(runId)
        _streamingAssistantText.value = null
        _errorText.value = err.message ?: "Unknown error"
      }
    }
  }

  fun abort() {
    currentRunJob?.cancel()
    currentRunJob = null
    clearPendingRuns()
    _streamingAssistantText.value = null
  }

  fun onDisconnected(message: String) {
    _healthOk.value = false
    _errorText.value = null
    clearPendingRuns()
    _streamingAssistantText.value = null
  }

  private fun bootstrap() {
    _errorText.value = null
    _healthOk.value = config.hasApiKey
    clearPendingRuns()
    _streamingAssistantText.value = null

    val key = _sessionKey.value
    val session = sessionStore.getSession(key)
    _sessionId.value = key
    _thinkingLevel.value = session.thinkingLevel

    _messages.value = session.messages.map { msg ->
      ChatMessage(
        id = msg.id,
        role = msg.role,
        content = listOf(ChatMessageContent(type = "text", text = msg.content)),
        timestampMs = msg.timestamp.toLong(),
      )
    }

    refreshSessions(limit = 50)
  }

  private fun armPendingRunTimeout(runId: String) {
    pendingRunTimeoutJobs[runId]?.cancel()
    pendingRunTimeoutJobs[runId] = scope.launch {
      delay(pendingRunTimeoutMs)
      val stillPending = synchronized(pendingRuns) { pendingRuns.contains(runId) }
      if (!stillPending) return@launch
      clearPendingRun(runId)
      _errorText.value = "Timed out waiting for a reply; try again."
    }
  }

  private fun clearPendingRun(runId: String) {
    pendingRunTimeoutJobs.remove(runId)?.cancel()
    synchronized(pendingRuns) {
      pendingRuns.remove(runId)
      _pendingRunCount.value = pendingRuns.size
    }
  }

  private fun clearPendingRuns() {
    for ((_, job) in pendingRunTimeoutJobs) job.cancel()
    pendingRunTimeoutJobs.clear()
    synchronized(pendingRuns) {
      pendingRuns.clear()
      _pendingRunCount.value = 0
    }
  }

  private fun normalizeThinking(raw: String): String =
    when (raw.trim().lowercase()) {
      "low" -> "low"
      "medium" -> "medium"
      "high" -> "high"
      else -> "off"
    }
}
