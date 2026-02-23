package ai.openclaw.android.agent

import android.content.Context
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.io.File
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

@Serializable
data class StoredMessage(
  val id: String = UUID.randomUUID().toString(),
  val role: String,
  val content: String,
  val timestamp: Double = System.currentTimeMillis().toDouble(),
)

@Serializable
data class StoredSession(
  val key: String,
  var displayName: String? = null,
  var messages: MutableList<StoredMessage> = mutableListOf(),
  var thinkingLevel: String = "off",
  var updatedAt: Double = System.currentTimeMillis().toDouble(),
)

class LocalSessionStore(context: Context) {
  private val baseDir = File(context.filesDir, "local-agent-sessions").also { it.mkdirs() }
  private val cache = ConcurrentHashMap<String, StoredSession>()
  private val json = Json { ignoreUnknownKeys = true; prettyPrint = false }

  fun getSession(key: String): StoredSession {
    cache[key]?.let { return it }
    val file = fileFor(key)
    if (file.exists()) {
      try {
        val session = json.decodeFromString<StoredSession>(file.readText())
        cache[key] = session
        return session
      } catch (_: Exception) {
        // Corrupted file; start fresh.
      }
    }
    val fresh = StoredSession(key = key)
    cache[key] = fresh
    return fresh
  }

  fun appendMessage(message: StoredMessage, sessionKey: String) {
    val session = getSession(sessionKey)
    session.messages.add(message)
    session.updatedAt = System.currentTimeMillis().toDouble()
    cache[sessionKey] = session
    persist(session)
  }

  fun setThinkingLevel(level: String, sessionKey: String) {
    val session = getSession(sessionKey)
    session.thinkingLevel = level
    cache[sessionKey] = session
    persist(session)
  }

  fun clearSession(key: String) {
    val session = getSession(key)
    session.messages.clear()
    session.updatedAt = System.currentTimeMillis().toDouble()
    cache[key] = session
    persist(session)
  }

  fun listSessions(): List<StoredSession> {
    val files = baseDir.listFiles { f -> f.extension == "json" } ?: emptyArray()
    val sessions = mutableListOf<StoredSession>()
    for (file in files) {
      try {
        val session = json.decodeFromString<StoredSession>(file.readText())
        sessions.add(session)
        cache[session.key] = session
      } catch (_: Exception) {
        // Skip corrupted files.
      }
    }
    return sessions.sortedByDescending { it.updatedAt }
  }

  private fun persist(session: StoredSession) {
    try {
      val file = fileFor(session.key)
      file.writeText(json.encodeToString(StoredSession.serializer(), session))
    } catch (_: Exception) {
      // Best effort.
    }
  }

  private fun fileFor(key: String): File {
    val safe = key.replace("/", "_").replace(":", "_")
    return File(baseDir, "$safe.json")
  }
}
