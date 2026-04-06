/**
 * Service Worker — receives events from universal.js, deduplicates,
 * batches, and forwards to local LLM Wiki server.
 */

const LOCAL_API = "http://localhost:8765";
const BATCH_DELAY_MS = 3000;   // wait before flushing batch
const MAX_QUEUE = 50;

// ── Queue & state ──────────────────────────────────────────────────────────
let _queue = [];
let _batchTimer = null;
let _seenUrls = new Set();     // in-memory dedup (cleared on SW restart)

async function getStats() {
  const data = await chrome.storage.local.get(["stats"]);
  return data.stats || { page_visits: 0, ai_conversations: 0, last_sync: null };
}

async function incStats(key) {
  const stats = await getStats();
  stats[key] = (stats[key] || 0) + 1;
  stats.last_sync = new Date().toISOString();
  await chrome.storage.local.set({ stats });
}

// ── Message router ─────────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "PAGE_VISIT") {
    handlePageVisit(msg.payload, sender.tab);
  } else if (msg.type === "AI_CONVERSATION") {
    handleAIConversation(msg.payload, sender.tab);
  } else if (msg.type === "GET_STATS") {
    getStats().then(sendResponse);
    return true;
  }
});

// ── Handlers ───────────────────────────────────────────────────────────────

function handlePageVisit(payload, tab) {
  const url = payload.url;

  // Dedup: skip if same URL seen in this session
  if (_seenUrls.has(url)) return;
  _seenUrls.add(url);
  if (_seenUrls.size > 500) {
    // Prevent unbounded growth
    const oldest = [..._seenUrls].slice(0, 100);
    oldest.forEach((u) => _seenUrls.delete(u));
  }

  _enqueue({
    source: "web",
    type: "page_visit",
    title: payload.title,
    body: payload.body,
    source_url: url,
    metadata: {
      hostname: payload.hostname,
      dwell_seconds: payload.dwell_seconds,
    },
  });
}

function handleAIConversation(payload, tab) {
  const key = `${payload.source}:${payload.source_url}`;
  if (_seenUrls.has(key)) return;
  _seenUrls.add(key);

  if (!payload.messages || payload.messages.length === 0) return;

  const body = payload.messages
    .map((m) => `**${m.role}**: ${m.content}`)
    .join("\n\n");

  _enqueue({
    source: payload.source,
    type: "ai_conversation",
    title: payload.title || `${payload.source} conversation`,
    body: body.slice(0, 8000),
    source_url: payload.source_url,
    metadata: { message_count: payload.messages.length },
  });
}

// ── Queue & flush ──────────────────────────────────────────────────────────

function _enqueue(item) {
  _queue.push(item);
  if (_queue.length >= MAX_QUEUE) {
    _flush();
  } else {
    clearTimeout(_batchTimer);
    _batchTimer = setTimeout(_flush, BATCH_DELAY_MS);
  }
}

async function _flush() {
  if (_queue.length === 0) return;
  const batch = _queue.splice(0);

  try {
    await fetch(`${LOCAL_API}/health`, { signal: AbortSignal.timeout(1500) });
  } catch {
    // Server not running — put items back
    _queue.unshift(...batch);
    return;
  }

  for (const item of batch) {
    try {
      const res = await fetch(`${LOCAL_API}/connectors/extension/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(item),
      });
      if (res.ok) {
        const type = item.type === "page_visit" ? "page_visits" : "ai_conversations";
        await incStats(type);
      }
    } catch (e) {
      console.warn("[llm-wiki] send failed:", e.message);
    }
  }

  console.log(`[llm-wiki] flushed ${batch.length} items`);
}
