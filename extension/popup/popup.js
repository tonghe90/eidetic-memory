const LOCAL_API = "http://localhost:8765";

const SKIP_HOSTNAMES = new Set([
  "localhost", "127.0.0.1", "accounts.google.com",
  "login.microsoftonline.com",
]);

async function init() {
  await checkServer();
  await loadStats();
  await showCurrentTab();
}

async function checkServer() {
  const bar = document.getElementById("server-status");
  try {
    const res = await fetch(`${LOCAL_API}/health`, {
      signal: AbortSignal.timeout(2000),
    });
    bar.textContent = "● 本地服务运行中";
    bar.className = "status-bar ok";
  } catch {
    bar.textContent = "● 本地服务未运行 — 请先启动 ./start.sh";
    bar.className = "status-bar err";
  }
}

async function loadStats() {
  const stats = await chrome.runtime.sendMessage({ type: "GET_STATS" });
  document.getElementById("pages-count").textContent = stats?.page_visits ?? 0;
  document.getElementById("ai-count").textContent = stats?.ai_conversations ?? 0;

  const lastSync = document.getElementById("last-sync");
  if (stats?.last_sync) {
    const d = new Date(stats.last_sync);
    lastSync.textContent = "上次: " + d.toLocaleString("zh-CN", {
      month: "numeric", day: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  }
}

async function showCurrentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) return;

  const urlEl = document.getElementById("current-url");
  const statusEl = document.getElementById("current-status");

  try {
    const url = new URL(tab.url);
    urlEl.textContent = url.hostname + url.pathname.slice(0, 40);

    const host = url.hostname.replace(/^www\./, "");
    if (SKIP_HOSTNAMES.has(host) || url.protocol === "chrome:") {
      statusEl.textContent = "— 跳过（系统页面）";
      statusEl.className = "current-status skipping";
    } else {
      statusEl.textContent = "● 正在捕获（停留 30s 后保存）";
      statusEl.className = "current-status capturing";
    }
  } catch {
    urlEl.textContent = tab.url?.slice(0, 50) || "—";
  }
}

init();
