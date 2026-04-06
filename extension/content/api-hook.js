/**
 * API interceptor — runs in MAIN world (has access to page's fetch/XHR).
 * Detects AI conversation API responses and forwards them via CustomEvent
 * to the ISOLATED world (universal.js) for sending to local server.
 *
 * Automatically covers: ChatGPT, Claude.ai, Perplexity, Gemini, Grok,
 * Notion AI, and any app that uses a fetch-based chat API.
 */

// ── Patterns that identify AI conversation API endpoints ──────────────────
const AI_API_PATTERNS = [
  /\/backend-api\/conversation/,          // ChatGPT
  /\/api\/.*chat_conversation/,           // Claude.ai
  /\/api\/answer/,                        // Perplexity
  /\/api\/generate/,                      // Ollama / local LLMs
  /\/v1\/messages/,                       // Anthropic API direct
  /\/v1\/chat\/completions/,              // OpenAI API / compatible
  /\/_next\/data\/.*chat/,                // Next.js based chat apps
  /\/api\/chat/,                          // Generic chat endpoints
  /\/api\/conversation/,                  // Generic conversation endpoints
];

// ── Intercept fetch ────────────────────────────────────────────────────────
const _origFetch = window.fetch;
window.fetch = async function (input, init) {
  const url = typeof input === "string" ? input : input?.url || "";
  const response = await _origFetch.apply(this, arguments);

  if (_isAIApi(url)) {
    _captureResponse(url, response.clone());
  }

  return response;
};

// ── Intercept XHR ──────────────────────────────────────────────────────────
const _origOpen = XMLHttpRequest.prototype.open;
const _origSend = XMLHttpRequest.prototype.send;

XMLHttpRequest.prototype.open = function (method, url) {
  this._llmUrl = url;
  return _origOpen.apply(this, arguments);
};

XMLHttpRequest.prototype.send = function () {
  if (this._llmUrl && _isAIApi(this._llmUrl)) {
    this.addEventListener("load", function () {
      try {
        const data = JSON.parse(this.responseText);
        _dispatchCapture(this._llmUrl, data);
      } catch {}
    });
  }
  return _origSend.apply(this, arguments);
};

// ── Helpers ────────────────────────────────────────────────────────────────

function _isAIApi(url) {
  return AI_API_PATTERNS.some((p) => p.test(url));
}

async function _captureResponse(url, response) {
  // Handle streaming (text/event-stream) and JSON responses
  const contentType = response.headers.get("content-type") || "";
  try {
    if (contentType.includes("application/json")) {
      const data = await response.json();
      _dispatchCapture(url, data);
    } else if (contentType.includes("text/event-stream")) {
      // SSE streaming — collect all chunks
      const reader = response.body.getReader();
      const chunks = [];
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(new TextDecoder().decode(value));
      }
      _dispatchCapture(url, { _raw_stream: chunks.join(""), _url: url });
    }
  } catch {}
}

function _dispatchCapture(url, data) {
  window.dispatchEvent(
    new CustomEvent("__llmwiki_api_capture__", {
      detail: { url, data, ts: Date.now() },
    })
  );
}
