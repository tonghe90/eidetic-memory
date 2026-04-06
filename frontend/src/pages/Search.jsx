import React, { useState, useRef } from "react";
import { getSourceFromUrl, getSourceIcon, getSourceLabel } from "../lib/sourceCatalog";

const EXAMPLES = [
  "最近找我申请 PhD 或实习的同学",
  "关于 LLM reasoning 的讨论",
  "React hooks 相关内容",
  "上周看过的论文",
];

export default function Search() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef(null);

  const handleSearch = async (q = query) => {
    const trimmed = q.trim();
    if (!trimmed) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch(`/search/?q=${encodeURIComponent(trimmed)}`);
      if (!res.ok) throw new Error(`服务器错误 ${res.status}`);
      setResult(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReindex = async () => {
    await fetch("/search/reindex", { method: "POST" });
    alert("索引已重建");
  };

  return (
    <div className="max-w-2xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">搜索</h2>
        <button
          onClick={handleReindex}
          className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          重建索引
        </button>
      </div>

      {/* Search box */}
      <div className="relative mb-4">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="自然语言搜索，例如：申请实习的同学..."
          className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 pr-24
                     text-sm text-white placeholder-gray-500
                     focus:outline-none focus:border-indigo-500 transition-colors"
          autoFocus
        />
        <button
          onClick={() => handleSearch()}
          disabled={loading || !query.trim()}
          className="absolute right-2 top-1/2 -translate-y-1/2
                     px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500
                     disabled:opacity-40 rounded-lg text-sm font-medium transition-colors"
        >
          {loading ? "搜索中..." : "搜索"}
        </button>
      </div>

      {/* Example queries */}
      {!result && !loading && (
        <div className="flex flex-wrap gap-2 mb-8">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              onClick={() => { setQuery(ex); handleSearch(ex); }}
              className="text-xs bg-gray-800 hover:bg-gray-700 text-gray-400
                         hover:text-white px-3 py-1.5 rounded-full transition-colors"
            >
              {ex}
            </button>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-900/30 border border-red-800 rounded-xl p-4 text-red-300 text-sm mb-4">
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Answer summary */}
          <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs bg-indigo-900/50 text-indigo-300 px-2 py-0.5 rounded-full">
                AI 回答
              </span>
              <span className="text-xs text-gray-500">
                基于 {result.result_count} 条结果
              </span>
            </div>
            <p className="text-sm leading-relaxed text-gray-200">{result.answer}</p>
          </div>

          {/* Structured items (e.g. applicants list) */}
          {result.items?.length > 0 && (
            <div className="space-y-3">
              {result.items.map((item, i) => (
                <ResultCard key={i} item={item} />
              ))}
            </div>
          )}

          {/* Sources */}
          {result.sources?.length > 0 && (
            <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
              <p className="text-xs font-medium text-gray-400 mb-2">来源</p>
              <div className="space-y-1.5">
                {result.sources.map((s, i) => (
                  <SourceLink key={i} source={s} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ResultCard({ item }) {
  const icon = getSourceIcon(item.source);
  const sourceLabel = getSourceLabel(item.source);

  return (
    <div className="bg-gray-900 rounded-xl p-4 border border-gray-800 hover:border-gray-700 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-sm mb-1 truncate">{item.title}</p>
          <p className="text-xs text-gray-400 leading-relaxed">{item.summary}</p>

          {/* Extra metadata fields */}
          {item.metadata && Object.keys(item.metadata).length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {Object.entries(item.metadata).map(([k, v]) =>
                v ? (
                  <span
                    key={k}
                    className="text-xs bg-gray-800 text-gray-300 px-2 py-0.5 rounded-full"
                  >
                    {v}
                  </span>
                ) : null
              )}
            </div>
          )}
        </div>

        {item.source_url && (
          <a
            href={item.source_url}
            target="_blank"
            rel="noopener noreferrer"
            title={`打开原始 ${sourceLabel}`}
            className="shrink-0 flex items-center gap-1 text-xs text-indigo-400
                       hover:text-indigo-300 transition-colors bg-indigo-900/30
                       px-2.5 py-1 rounded-lg"
          >
            <span>{icon}</span>
            <span>{sourceLabel}</span>
            <span className="opacity-60">↗</span>
          </a>
        )}
      </div>
    </div>
  );
}

function SourceLink({ source }) {
  const sourceType = getSourceFromUrl(source.url);
  const icon = sourceType ? getSourceIcon(sourceType) : "📄";
  const label = source.label || (sourceType ? getSourceLabel(sourceType) : "来源");

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm">{icon}</span>
      {source.url ? (
        <a
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-indigo-400 hover:text-indigo-300 truncate transition-colors"
        >
          {label}
        </a>
      ) : (
        <span className="text-xs text-gray-500 truncate">{label}</span>
      )}
    </div>
  );
}
