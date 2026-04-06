import React, { useEffect, useState } from "react";
import { getAuthGuide, getSourceIcon, SOURCE_ORDER } from "../lib/sourceCatalog";

export default function Sources() {
  const [connectors, setConnectors] = useState([]);
  const [syncing, setSyncing] = useState({});
  const [loading, setLoading] = useState({});
  const [polling, setPolling] = useState(null);
  const [syncResults, setSyncResults] = useState({});

  const fetchConnectors = async () => {
    const res = await fetch("/connectors/");
    const all = await res.json();
    const visible = SOURCE_ORDER
      .map((name) => all.find((connector) => connector.name === name))
      .filter(Boolean);
    setConnectors(visible);
  };

  useEffect(() => {
    fetchConnectors();
  }, []);

  // Poll after opening auth window
  useEffect(() => {
    if (!polling) return;
    const id = setInterval(async () => {
      const res = await fetch("/connectors/setup-status");
      const statuses = await res.json();
      if (statuses[polling]) {
        setPolling(null);
        fetchConnectors();
        clearInterval(id);
      }
    }, 2000);
    return () => clearInterval(id);
  }, [polling]);

  const handleAuth = async (name) => {
    setLoading((p) => ({ ...p, [name]: true }));
    const res = await fetch(`/connectors/${name}/auth-url`);
    const data = await res.json();
    if (data.mode === "popup") {
      window.open(data.url, "_blank", "width=500,height=700");
      setPolling(name);
    } else if (data.mode === "system") {
      // macOS system preferences — open via URL scheme, show instructions
      window.open(data.url, "_blank");
      alert(data.instructions || "请在系统设置中完成授权后，点击「检测」按钮。");
    } else {
      window.open(data.url, "_blank");
      setPolling(name);
    }
    setLoading((p) => ({ ...p, [name]: false }));
  };

  const handleDetect = async (name) => {
    const res = await fetch("/connectors/setup-status");
    const statuses = await res.json();
    if (statuses[name]) fetchConnectors();
    else alert(`未检测到 ${name} 授权，请确认已完成系统设置后重试。`);
  };

  const handleSync = async (name) => {
    setSyncing((p) => ({ ...p, [name]: true }));
    try {
      const res = await fetch(`/connectors/${name}/sync`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `同步失败 (${res.status})`);
      }
      setSyncResults((p) => ({ ...p, [name]: data }));
      fetchConnectors();
    } catch (error) {
      alert(error.message || "同步失败");
    } finally {
      setSyncing((p) => ({ ...p, [name]: false }));
    }
  };

  return (
    <div className="max-w-2xl">
      <h2 className="text-2xl font-bold mb-6">数据源</h2>

      <div className="space-y-4">
        {connectors.map((c) => (
          <div key={c.name} className="bg-gray-900 rounded-xl p-5 border border-gray-800">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <span className="text-2xl">{getSourceIcon(c.name)}</span>
                <div>
                  <p className="font-semibold">{c.display_name}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {c.authenticated ? (
                      <span className="text-green-400">● 已授权</span>
                    ) : (
                      <span className="text-gray-500">● 未授权</span>
                    )}
                    {c.last_sync && (
                      <span className="ml-2 text-gray-500">
                        上次同步 {new Date(c.last_sync).toLocaleString("zh-CN")}
                      </span>
                    )}
                  </p>
                </div>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => handleAuth(c.name)}
                  disabled={loading[c.name]}
                  className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm
                             disabled:opacity-40 transition-colors"
                >
                  {loading[c.name]
                    ? "跳转中..."
                    : c.authenticated
                    ? "重新授权"
                    : c.auth_type === "local_db"
                    ? "打开设置"
                    : "授权"}
                </button>

                {c.auth_type === "local_db" && !c.authenticated && (
                  <button
                    onClick={() => handleDetect(c.name)}
                    className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors"
                  >
                    检测
                  </button>
                )}

                {c.authenticated && c.auth_type !== "extension" && (
                  <button
                    onClick={() => handleSync(c.name)}
                    disabled={syncing[c.name]}
                    className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm
                               disabled:opacity-40 transition-colors"
                  >
                    {syncing[c.name] ? "同步中..." : "同步"}
                  </button>
                )}
              </div>
            </div>

            <p className="text-xs text-gray-500 mt-3">{getAuthGuide(c.name)}</p>

            {polling === c.name && !c.authenticated && (
              <div className="mt-2 flex items-center gap-2 text-xs text-indigo-400">
                <div className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-pulse" />
                等待授权完成...
              </div>
            )}

            {syncResults[c.name] && (
              <div className="mt-3 text-xs bg-gray-800 rounded-lg px-3 py-2 text-gray-300">
                获取 {syncResults[c.name].fetched} 条 · 新增 {syncResults[c.name].inserted} 条 ·
                重复跳过 {syncResults[c.name].duplicate_skipped} 条
              </div>
            )}
          </div>
        ))}

        {connectors.length === 0 && (
          <p className="text-gray-500 text-sm">正在加载...</p>
        )}
      </div>
    </div>
  );
}
