import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { SOURCE_ORDER, getSourceIcon } from "../lib/sourceCatalog";

const STEPS = [
  {
    key: "gmail",
    label: "Gmail",
    type: "oauth",
    description: "授权只读邮件访问权限，用于采集邮件内容。",
    required: true,
  },
  {
    key: "googledocs",
    label: "Google Docs",
    type: "oauth",
    description: "授权只读 Google Docs 访问权限，用于采集文档正文与原始链接。",
    required: false,
  },
  {
    key: "chrome",
    label: "Google Chrome 浏览记录",
    type: "system",
    description: "在系统设置 → 隐私与安全 → 完全磁盘访问中授权，用于采集浏览记录。",
    required: false,
  },
  {
    key: "chatgpt",
    label: "ChatGPT",
    type: "extension",
    description: "打开 ChatGPT 后，浏览器扩展会自动同步对话历史。",
    required: false,
  },
  {
    key: "claude",
    label: "Claude.ai",
    type: "extension",
    description: "打开 Claude.ai 后，浏览器扩展会自动同步对话历史。",
    required: false,
  },
].sort((a, b) => SOURCE_ORDER.indexOf(a.key) - SOURCE_ORDER.indexOf(b.key));

export default function Onboarding() {
  const navigate = useNavigate();
  const [statuses, setStatuses] = useState({});
  const [loading, setLoading] = useState({});
  const [polling, setPolling] = useState(null); // key being polled

  const fetchStatuses = async () => {
    const res = await fetch("/connectors/setup-status");
    setStatuses(await res.json());
  };

  useEffect(() => {
    fetchStatuses();
  }, []);

  // Poll after opening a window until auth detected
  useEffect(() => {
    if (!polling) return;
    const id = setInterval(async () => {
      await fetchStatuses();
      setStatuses((prev) => {
        if (prev[polling]) {
          setPolling(null);
          clearInterval(id);
        }
        return prev;
      });
    }, 2000);
    return () => clearInterval(id);
  }, [polling]);

  const handleAuth = async (key) => {
    setLoading((p) => ({ ...p, [key]: true }));
    const res = await fetch(`/connectors/${key}/auth-url`);
    const data = await res.json();
    if (data.mode === "popup") {
      window.open(data.url, "_blank", "width=500,height=700");
      setPolling(key);
    } else if (data.mode === "system") {
      window.open(data.url, "_blank");
      // For system-level auth, user manually confirms via "检测" button — no auto-poll
    } else {
      window.open(data.url, "_blank");
      setPolling(key);
    }
    setLoading((p) => ({ ...p, [key]: false }));
  };

  const handleDetect = async (key) => {
    const res = await fetch("/connectors/setup-status");
    const statuses = await res.json();
    if (statuses[key]) {
      setStatuses((p) => ({ ...p, [key]: true }));
    } else {
      alert("未检测到授权，请确认已在系统设置中完成操作。");
    }
  };

  const allRequired = STEPS.filter((s) => s.required).every((s) => statuses[s.key]);
  const anyAuthed = STEPS.some((s) => statuses[s.key]);

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="text-3xl font-bold text-white mb-2">欢迎使用 LLM Wiki</h1>
          <p className="text-gray-400">授权数据源，开始构建你的个人知识库</p>
        </div>

        {/* Steps */}
        <div className="space-y-4 mb-8">
          {STEPS.map((step) => {
            const authed = statuses[step.key];
            const isLoading = loading[step.key];
            const isPolling = polling === step.key;

            return (
              <div
                key={step.key}
                className={`rounded-xl p-5 border transition-colors ${
                  authed
                    ? "bg-green-950/30 border-green-800"
                    : "bg-gray-900 border-gray-800"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">{getSourceIcon(step.key)}</span>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold">{step.label}</span>
                        {!step.required && (
                          <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">
                            可选
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5">{step.description}</p>
                    </div>
                  </div>

                  {authed ? (
                    <div className="flex items-center gap-1.5 text-green-400 text-sm font-medium">
                      <span className="w-2 h-2 bg-green-400 rounded-full" />
                      已授权
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleAuth(step.key)}
                        disabled={isLoading}
                        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm
                                   font-medium transition-colors disabled:opacity-50 whitespace-nowrap"
                      >
                        {isLoading ? "跳转中..." : step.type === "system" ? "打开设置" : "授权"}
                      </button>
                      {step.type === "system" && (
                        <button
                          onClick={() => handleDetect(step.key)}
                          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm
                                     font-medium transition-colors whitespace-nowrap"
                        >
                          检测
                        </button>
                      )}
                    </div>
                  )}
                </div>

                {isPolling && !authed && (
                  <div className="mt-3 flex items-center gap-2 text-xs text-indigo-400">
                    <div className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-pulse" />
                    {step.type === "extension"
                      ? "请在打开的页面中确认，扩展检测到登录后将自动完成..."
                      : "等待 Google 授权回调..."}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-3">
          {allRequired && (
            <button
              onClick={() => navigate("/")}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 rounded-xl
                         font-semibold text-white transition-colors"
            >
              开始使用 →
            </button>
          )}
          {!allRequired && anyAuthed && (
            <button
              onClick={() => navigate("/")}
              className="w-full py-3 bg-gray-800 hover:bg-gray-700 rounded-xl
                         text-gray-300 text-sm transition-colors"
            >
              跳过，稍后配置
            </button>
          )}
          {!anyAuthed && (
            <p className="text-center text-xs text-gray-500">
              至少完成 Gmail 授权后可开始使用，Google Docs 与 Google Chrome 可稍后补充
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
