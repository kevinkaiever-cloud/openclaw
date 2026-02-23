package ai.openclaw.android.agent

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.util.concurrent.TimeUnit

data class CompletionResponse(
  val text: String,
  val stopReason: String?,
  val inputTokens: Int?,
  val outputTokens: Int?,
)

class LocalAgentService {
  private val client = OkHttpClient.Builder()
    .connectTimeout(30, TimeUnit.SECONDS)
    .readTimeout(120, TimeUnit.SECONDS)
    .writeTimeout(30, TimeUnit.SECONDS)
    .build()

  suspend fun sendCompletion(
    messages: List<StoredMessage>,
    systemPrompt: String,
    provider: AIProvider,
    model: String,
    apiKey: String,
    maxTokens: Int,
    customEndpoint: String,
    onStream: (String) -> Unit,
  ): CompletionResponse = withContext(Dispatchers.IO) {
    require(apiKey.isNotEmpty()) { "No API key configured. Please set your API key in Settings." }

    when (provider) {
      AIProvider.ANTHROPIC -> callAnthropic(messages, systemPrompt, model, apiKey, maxTokens, customEndpoint, onStream)
      AIProvider.OPENAI -> callOpenAI(messages, systemPrompt, model, apiKey, maxTokens, customEndpoint, onStream)
    }
  }

  private fun callAnthropic(
    messages: List<StoredMessage>,
    systemPrompt: String,
    model: String,
    apiKey: String,
    maxTokens: Int,
    customEndpoint: String,
    onStream: (String) -> Unit,
  ): CompletionResponse {
    val baseUrl = customEndpoint.ifEmpty { "https://api.anthropic.com" }

    val msgArray = JSONArray().apply {
      for (msg in messages) {
        put(JSONObject().apply {
          put("role", msg.role)
          put("content", msg.content)
        })
      }
    }

    val body = JSONObject().apply {
      put("model", model)
      put("max_tokens", maxTokens)
      put("system", systemPrompt)
      put("messages", msgArray)
      put("stream", true)
    }

    val request = Request.Builder()
      .url("$baseUrl/v1/messages")
      .post(body.toString().toRequestBody("application/json".toMediaType()))
      .addHeader("x-api-key", apiKey)
      .addHeader("anthropic-version", "2023-06-01")
      .addHeader("Content-Type", "application/json")
      .build()

    return executeStreaming(request, "anthropic", onStream)
  }

  private fun callOpenAI(
    messages: List<StoredMessage>,
    systemPrompt: String,
    model: String,
    apiKey: String,
    maxTokens: Int,
    customEndpoint: String,
    onStream: (String) -> Unit,
  ): CompletionResponse {
    val baseUrl = customEndpoint.ifEmpty { "https://api.openai.com" }

    val msgArray = JSONArray().apply {
      put(JSONObject().apply {
        put("role", "system")
        put("content", systemPrompt)
      })
      for (msg in messages) {
        put(JSONObject().apply {
          put("role", msg.role)
          put("content", msg.content)
        })
      }
    }

    val body = JSONObject().apply {
      put("model", model)
      put("max_tokens", maxTokens)
      put("messages", msgArray)
      put("stream", true)
    }

    val request = Request.Builder()
      .url("$baseUrl/v1/chat/completions")
      .post(body.toString().toRequestBody("application/json".toMediaType()))
      .addHeader("Authorization", "Bearer $apiKey")
      .addHeader("Content-Type", "application/json")
      .build()

    return executeStreaming(request, "openai", onStream)
  }

  private fun executeStreaming(
    request: Request,
    provider: String,
    onStream: (String) -> Unit,
  ): CompletionResponse {
    val response = client.newCall(request).execute()
    if (!response.isSuccessful) {
      val errorBody = response.body?.string() ?: "Unknown error"
      throw RuntimeException("API error (${response.code}): $errorBody")
    }

    val reader = BufferedReader(InputStreamReader(response.body!!.byteStream()))
    var fullText = ""
    var stopReason: String? = null
    var inputTokens: Int? = null
    var outputTokens: Int? = null

    try {
      var line: String?
      while (reader.readLine().also { line = it } != null) {
        val l = line ?: continue
        if (!l.startsWith("data: ")) continue
        val jsonStr = l.removePrefix("data: ").trim()
        if (jsonStr == "[DONE]") break

        try {
          val event = JSONObject(jsonStr)
          when (provider) {
            "anthropic" -> {
              when (event.optString("type")) {
                "content_block_delta" -> {
                  val delta = event.optJSONObject("delta")
                  val text = delta?.optString("text")
                  if (!text.isNullOrEmpty()) {
                    fullText += text
                    onStream(fullText)
                  }
                }
                "message_delta" -> {
                  val delta = event.optJSONObject("delta")
                  stopReason = delta?.optString("stop_reason")
                  val usage = event.optJSONObject("usage")
                  if (usage != null) outputTokens = usage.optInt("output_tokens", 0)
                }
                "message_start" -> {
                  val message = event.optJSONObject("message")
                  val usage = message?.optJSONObject("usage")
                  if (usage != null) inputTokens = usage.optInt("input_tokens", 0)
                }
              }
            }
            "openai" -> {
              val choices = event.optJSONArray("choices")
              if (choices != null && choices.length() > 0) {
                val first = choices.getJSONObject(0)
                val delta = first.optJSONObject("delta")
                val text = delta?.optString("content")
                if (!text.isNullOrEmpty()) {
                  fullText += text
                  onStream(fullText)
                }
                val finish = first.optString("finish_reason", null)
                if (finish != null) stopReason = finish
              }
              val usage = event.optJSONObject("usage")
              if (usage != null) {
                inputTokens = usage.optInt("prompt_tokens", 0)
                outputTokens = usage.optInt("completion_tokens", 0)
              }
            }
          }
        } catch (_: Exception) {
          // Skip malformed events.
        }
      }
    } finally {
      reader.close()
      response.close()
    }

    return CompletionResponse(
      text = fullText,
      stopReason = stopReason,
      inputTokens = inputTokens,
      outputTokens = outputTokens,
    )
  }
}
