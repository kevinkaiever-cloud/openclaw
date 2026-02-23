package ai.openclaw.android.agent

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKeys

enum class AIProvider(val id: String, val displayName: String, val defaultModel: String) {
  ANTHROPIC("anthropic", "Anthropic (Claude)", "claude-sonnet-4-20250514"),
  OPENAI("openai", "OpenAI (GPT)", "gpt-4o");

  val availableModels: List<String>
    get() = when (this) {
      ANTHROPIC -> listOf(
        "claude-sonnet-4-20250514",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-haiku-20240307",
      )
      OPENAI -> listOf("gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1-mini")
    }

  companion object {
    fun fromId(id: String): AIProvider = entries.find { it.id == id } ?: ANTHROPIC
  }
}

class LocalAgentConfig(context: Context) {
  private val prefs: SharedPreferences = context.getSharedPreferences("local_agent", Context.MODE_PRIVATE)

  private val securePrefs: SharedPreferences by lazy {
    val masterKey = MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC)
    EncryptedSharedPreferences.create(
      "local_agent_secure",
      masterKey,
      context,
      EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
      EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )
  }

  var isEnabled: Boolean
    get() = prefs.getBoolean("enabled", false)
    set(value) = prefs.edit().putBoolean("enabled", value).apply()

  var provider: AIProvider
    get() = AIProvider.fromId(prefs.getString("provider", "anthropic") ?: "anthropic")
    set(value) = prefs.edit().putString("provider", value.id).apply()

  var model: String
    get() = prefs.getString("model", null)?.takeIf { it.isNotEmpty() } ?: provider.defaultModel
    set(value) = prefs.edit().putString("model", value).apply()

  var systemPrompt: String
    get() = prefs.getString("systemPrompt", null)
      ?: "You are a helpful AI assistant running locally on a mobile device. Be concise and helpful."
    set(value) = prefs.edit().putString("systemPrompt", value).apply()

  var maxTokens: Int
    get() = prefs.getInt("maxTokens", 4096)
    set(value) = prefs.edit().putInt("maxTokens", value).apply()

  var customEndpoint: String
    get() = prefs.getString("customEndpoint", "") ?: ""
    set(value) = prefs.edit().putString("customEndpoint", value).apply()

  val hasApiKey: Boolean
    get() = getApiKey(provider).isNotEmpty()

  fun getApiKey(provider: AIProvider): String =
    securePrefs.getString("apiKey.${provider.id}", "") ?: ""

  fun setApiKey(key: String, provider: AIProvider) {
    securePrefs.edit().putString("apiKey.${provider.id}", key).apply()
  }
}
