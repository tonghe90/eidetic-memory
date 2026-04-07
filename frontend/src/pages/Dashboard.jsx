import React, { useEffect, useState } from "react";
import { SOURCE_ORDER, getSourceLabel } from "../lib/sourceCatalog";

const SOURCE_COLORS = {
  gmail: "bg-red-500",
  googledocs: "bg-emerald-500",
  chrome: "bg-blue-500",
  chatgpt: "bg-green-500",
  claude: "bg-purple-500",
};

export default function Dashboard() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [startResult, setStartResult] = useState(null);

  const fetchStatus = async () => {
    const res = await fetch("/ingest/status");
    const data = await res.json();
    setStatus(data);
  };

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, 3000);
    return () => clearInterval(id);
  }, []);

  const handleIngest = async () => {
    setLoading(true);
    const res = await fetch("/ingest/start", { method: "POST" });
    const data = await res.json();
    setStartResult(data);
    setLoading(false);
    fetchStatus();
  };

  const pendingTotal = status
    ? Object.values(status.pending_by_source || {}).reduce((a, b) => a + b, 0)
    : 0;

  const lastReport = status?.last_report || {};

  return (
    <div className="max-w-3xl">
      <h2 className="text-2xl font-bold mb-6">Dashboard</h2>

      {/* Pending cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 mb-8">
        {SOURCE_ORDER.map((key) => {
          const pending = status?.pending_by_source?.[key] ?? 0;
          const total = status?.total_by_source?.[key] ?? 0;
          return (
            <div key={key} className="bg-gray-900 rounded-xl p-4 border border-gray-800">
              <div className={`w-2 h-2 rounded-full mb-3 ${SOURCE_COLORS[key]}`} />
              <p className="text-xs text-gray-400 mb-1">{getSourceLabel(key)}</p>
              <p className="text-2xl font-bold">{pending}</p>
              <p className="text-xs text-gray-500">待摄取 / {total} 总计</p>
            </div>
          );
        })}
      </div>

      {/* Ingest button */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="font-semibold">待摄取内容</p>
            <p className="text-3xl font-bold mt-1">{pendingTotal} 条</p>
          </div>
          <button
            onClick={handleIngest}
            disabled={loading || status?.running || status?.scheduled || pendingTotal === 0}
            className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40
                       disabled:cursor-not-allowed rounded-lg font-semibold transition-colors"
          >
            {status?.running
              ? "摄取中..."
              : status?.scheduled
              ? "已排队"
              : loading
              ? "启动中..."
              : "开始摄取"}
          </button>
        </div>
        {status?.running && (
          <div className="flex items-center gap-2 text-sm text-indigo-400">
            <div className="w-2 h-2 bg-indigo-400 rounded-full animate-pulse" />
            LLM 正在处理中，请稍候...
          </div>
        )}
        {status?.scheduled && (
          <div className="mt-3 text-sm text-amber-300">
            已排队，计划在{" "}
            {new Date(status.scheduled_for).toLocaleString("zh-CN")} 自动开始。
            {status.llm_provider === "ollama" && status.ollama_schedule_enabled && (
              <span className="text-xs text-gray-400 ml-2">
                本地模型运行窗口：{status.ollama_schedule_start} - {status.ollama_schedule_end}
              </span>
            )}
          </div>
        )}
        {startResult?.status === "scheduled" && !status?.scheduled && (
          <div className="mt-3 text-sm text-amber-300">
            已加入排队，将在 {new Date(startResult.scheduled_for).toLocaleString("zh-CN")} 启动。
          </div>
        )}
      </div>

      {/* Last report */}
      {lastReport.pages?.length > 0 && (
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
          <p className="font-semibold mb-3">上次摄取结果</p>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <Stat label="处理" value={lastReport.total_processed ?? 0} />
            <Stat label="Wiki 页面" value={lastReport.created ?? 0} />
            <Stat label="跳过" value={lastReport.skipped ?? 0} />
          </div>
          <p className="text-xs text-gray-400 font-medium mb-2">写入页面：</p>
          <ul className="space-y-1">
            {lastReport.pages.map((p) => (
              <li key={p} className="text-xs text-gray-400 font-mono truncate">
                {p}
              </li>
            ))}
          </ul>
        </div>
      )}

      {lastReport.error && (
        <div className="bg-red-900/30 border border-red-700 rounded-xl p-4 text-red-300 text-sm">
          错误：{lastReport.error}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="text-center">
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs text-gray-400">{label}</p>
    </div>
  );
}
