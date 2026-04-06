/**
 * Universal content script — ISOLATED world.
 * 1. Captures page content (article text) after meaningful dwell time.
 * 2. Receives AI API captures from api-hook.js via CustomEvent.
 * 3. Sends everything to background.js via chrome.runtime.sendMessage.
 */

const MIN_DWELL_SECONDS = 30;   // ignore quick bounces
const MAX_BODY_CHARS = 6000;

// ── Skip rules — don't capture these ──────────────────────────────────────
const SKIP_HOSTNAMES = new Set([
  "localhost", "127.0.0.1",
  "accounts.google.com", "login.microsoftonline.com",
  "github.com",           // mostly code — low signal for wiki
]);

const SKIP_PATH_PATTERNS = [
  /^\/(login|signin|signup|logout|auth)/i,
  /^\/(search|find)\?/i,
];

const SKIP_TITLE_PATTERNS = [
  /new tab/i, /404/i, /error/i,
];

// ── Page visit capture ─────────────────────────────────────────────────────
let _entryTime = Date.now();
let _sent = false;

function _shouldSkipPage() {
  const host = location.hostname.replace(/^www\./, "");
  if (SKIP_HOSTNAMES.has(host)) return true;
  if (SKIP_PATH_PATTERNS.some((p) => p.test(location.pathname + location.search))) return true;
  if (SKIP_TITLE_PATTERNS.some((p) => p.test(document.title))) return true;
  return false;
}

function _extractPageContent() {
  // Remove nav, footer, sidebars, scripts, styles
  const clone = document.body.cloneNode(true);
  for (const el of clone.querySelectorAll(
    "nav, footer, aside, header, script, style, noscript, [role=banner], [role=navigation], .ad, .ads, .advertisement"
  )) {
    el.remove();
  }

  // Prefer article / main content
  const main =
    clone.querySelector("article") ||
    clone.querySelector('[role="main"]') ||
    clone.querySelector("main") ||
    clone;

  const text = main.innerText || main.textContent || "";
  return text.replace(/\s+/g, " ").trim().slice(0, MAX_BODY_CHARS);
}

function _trySendPageVisit() {
  if (_sent || _shouldSkipPage()) return;

  const dwellSecs = (Date.now() - _entryTime) / 1000;
  if (dwellSecs < MIN_DWELL_SECONDS) return;

  const body = _extractPageContent();
  if (body.length < 100) return;

  _sent = true;
  chrome.runtime.sendMessage({
    type: "PAGE_VISIT",
    payload: {
      url: location.href,
      title: document.title,
      body,
      dwell_seconds: Math.round(dwellSecs),
      hostname: location.hostname,
    },
  });
}

// Capture on page hide (tab switch, close, navigate away)
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") _trySendPageVisit();
});
window.addEventListener("pagehide", _trySendPageVisit);

// Also try after 2 min of active reading
setTimeout(_trySendPageVisit, 120_000);

// ── AI API capture (from MAIN world via CustomEvent) ──────────────────────
window.addEventListener("__llmwiki_api_capture__", (e) => {
  const { url, data } = e.detail;
  const parsed = _parseAIResponse(url, data);
  if (!parsed) return;

  chrome.runtime.sendMessage({
    type: "AI_CONVERSATION",
    payload: {
      source: parsed.source,
      source_url: location.href,
      title: parsed.title || document.title,
      messages: parsed.messages,
    },
  });
});

// ── AI response parsers ────────────────────────────────────────────────────

function _parseAIResponse(url, data) {
  // ChatGPT: GET /backend-api/conversation/{id} → full conversation object
  if (url.includes("/backend-api/conversation/") && data.mapping) {
    return {
      source: "chatgpt",
      title: data.title,
      messages: _parseChatGPTMapping(data.mapping),
    };
  }

  // Claude: GET /api/.../chat_conversations/{id} → {chat_messages: [...]}
  if (url.includes("chat_conversation") && Array.isArray(data.chat_messages)) {
    return {
      source: "claude",
      title: data.name,
      messages: data.chat_messages.map((m) => ({
        role: m.sender === "human" ? "user" : "assistant",
        content: typeof m.text === "string" ? m.text : "",
      })).filter((m) => m.content),
    };
  }

  // Generic OpenAI-compatible: {choices: [{message: {role, content}}]}
  if (Array.isArray(data.choices) && data.choices[0]?.message) {
    return {
      source: _sourceFromUrl(url),
      title: null,
      messages: [data.choices[0].message],
    };
  }

  // Streaming response: try to extract text from SSE chunks
  if (data._raw_stream) {
    const text = _parseSSEStream(data._raw_stream);
    if (text.length > 50) {
      return {
        source: _sourceFromUrl(data._url || url),
        title: null,
        messages: [{ role: "assistant", content: text }],
      };
    }
  }

  return null;
}

function _parseChatGPTMapping(mapping) {
  const messages = [];
  let currentId = Object.keys(mapping).find((id) => !mapping[id].parent);
  const visited = new Set();

  while (currentId && !visited.has(currentId)) {
    visited.add(currentId);
    const node = mapping[currentId];
    if (!node) break;
    const msg = node.message;
    if (msg?.content?.parts && msg.author?.role !== "system") {
      const text = msg.content.parts.filter((p) => typeof p === "string").join("").trim();
      if (text) messages.push({ role: msg.author.role, content: text });
    }
    currentId = node.children?.[0] || null;
  }
  return messages;
}

function _parseSSEStream(raw) {
  // Extract text from SSE data: lines like `data: {"delta":{"text":"..."}}``
  const texts = [];
  for (const line of raw.split("\n")) {
    if (!line.startsWith("data: ")) continue;
    try {
      const obj = JSON.parse(line.slice(6));
      const text =
        obj.delta?.text ||
        obj.choices?.[0]?.delta?.content ||
        obj.completion ||
        "";
      if (text) texts.push(text);
    } catch {}
  }
  return texts.join("");
}

function _sourceFromUrl(url) {
  if (url.includes("chatgpt.com")) return "chatgpt";
  if (url.includes("claude.ai")) return "claude";
  if (url.includes("perplexity.ai")) return "perplexity";
  if (url.includes("gemini.google.com")) return "gemini";
  if (url.includes("grok.com") || url.includes("x.com/i/grok")) return "grok";
  return "ai_app";
}
