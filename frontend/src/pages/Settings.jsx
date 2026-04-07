import React, { useEffect, useState } from "react";

export default function Settings() {
  const [form, setForm] = useState({
    llm_provider: "claude",
    anthropic_api_key: "",
    openai_api_key: "",
    ollama_base_url: "http://127.0.0.1:11434",
    ollama_model: "gemma4:26b",
    ollama_schedule_enabled: false,
    ollama_schedule_start: "22:00",
    ollama_schedule_end: "09:00",
    wiki_path: "",
  });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetch("/settings/")
      .then((r) => r.json())
      .then((data) =>
        setForm({
          llm_provider: data.llm_provider || "claude",
          anthropic_api_key: data.anthropic_api_key === "***" ? "" : data.anthropic_api_key,
          openai_api_key: data.openai_api_key === "***" ? "" : data.openai_api_key,
          ollama_base_url: data.ollama_base_url || "http://127.0.0.1:11434",
          ollama_model: data.ollama_model || "gemma4:26b",
          ollama_schedule_enabled: !!data.ollama_schedule_enabled,
          ollama_schedule_start: data.ollama_schedule_start || "22:00",
          ollama_schedule_end: data.ollama_schedule_end || "09:00",
          wiki_path: data.wiki_path || "",
        })
      );
  }, []);

  const handleSave = async () => {
    const body = {};
    if (form.llm_provider) body.llm_provider = form.llm_provider;
    if (form.anthropic_api_key) body.anthropic_api_key = form.anthropic_api_key;
    if (form.openai_api_key) body.openai_api_key = form.openai_api_key;
    if (form.ollama_base_url) body.ollama_base_url = form.ollama_base_url;
    if (form.ollama_model) body.ollama_model = form.ollama_model;
    body.ollama_schedule_enabled = form.ollama_schedule_enabled;
    if (form.ollama_schedule_start) body.ollama_schedule_start = form.ollama_schedule_start;
    if (form.ollama_schedule_end) body.ollama_schedule_end = form.ollama_schedule_end;
    if (form.wiki_path) body.wiki_path = form.wiki_path;

    await fetch("/settings/", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="max-w-xl">
      <h2 className="text-2xl font-bold mb-6">设置</h2>

      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 space-y-6">

        {/* LLM Provider */}
        <div>
          <label className="block text-sm font-medium mb-2">LLM 提供商</label>
          <div className="flex gap-3">
            {["claude", "openai", "ollama"].map((p) => (
              <button
                key={p}
                onClick={() => setForm((f) => ({ ...f, llm_provider: p }))}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  form.llm_provider === p
                    ? "bg-indigo-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:text-white"
                }`}
              >
                {p === "claude"
                  ? "Claude (Anthropic)"
                  : p === "openai"
                  ? "GPT-4o (OpenAI)"
                  : "本地模型 (Ollama)"}
              </button>
            ))}
          </div>
        </div>

        {/* API Keys */}
        {form.llm_provider === "claude" && (
          <Field
            label="Anthropic API Key"
            value={form.anthropic_api_key}
            placeholder="sk-ant-..."
            onChange={(v) => setForm((f) => ({ ...f, anthropic_api_key: v }))}
          />
        )}
        {form.llm_provider === "openai" && (
          <Field
            label="OpenAI API Key"
            value={form.openai_api_key}
            placeholder="sk-..."
            onChange={(v) => setForm((f) => ({ ...f, openai_api_key: v }))}
          />
        )}
        {form.llm_provider === "ollama" && (
          <>
            <Field
              label="Ollama Base URL"
              value={form.ollama_base_url}
              placeholder="http://127.0.0.1:11434"
              onChange={(v) => setForm((f) => ({ ...f, ollama_base_url: v }))}
            />
            <Field
              label="Ollama 模型名"
              value={form.ollama_model}
              placeholder="gemma4:26b"
              onChange={(v) => setForm((f) => ({ ...f, ollama_model: v }))}
            />
            <p className="text-xs text-gray-400 -mt-3">
              例如填写你本地 Ollama 已拉取的模型名；保存后，分类、搜索回答与摄取都会走本地模型。
            </p>
            <div className="rounded-lg border border-gray-800 bg-gray-950/60 p-4 space-y-4">
              <label className="flex items-center gap-3 text-sm">
                <input
                  type="checkbox"
                  checked={form.ollama_schedule_enabled}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, ollama_schedule_enabled: e.target.checked }))
                  }
                  className="h-4 w-4 rounded border-gray-700 bg-gray-800 text-indigo-500"
                />
                <span>仅在低占用时段运行本地模型任务</span>
              </label>

              {form.ollama_schedule_enabled && (
                <div className="grid grid-cols-2 gap-4">
                  <TimeField
                    label="开始时间"
                    value={form.ollama_schedule_start}
                    onChange={(v) => setForm((f) => ({ ...f, ollama_schedule_start: v }))}
                  />
                  <TimeField
                    label="结束时间"
                    value={form.ollama_schedule_end}
                    onChange={(v) => setForm((f) => ({ ...f, ollama_schedule_end: v }))}
                  />
                </div>
              )}

              <p className="text-xs text-gray-500">
                支持跨天窗口，例如 22:00 到次日 09:00。若当前不在窗口内，点击“开始摄取”会先排队，到允许时段自动开始。
              </p>
            </div>
          </>
        )}

        {/* Wiki path */}
        <Field
          label="Wiki 路径（Obsidian Vault 根目录）"
          value={form.wiki_path}
          placeholder="./wiki"
          onChange={(v) => setForm((f) => ({ ...f, wiki_path: v }))}
        />

        <button
          onClick={handleSave}
          className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 rounded-lg font-semibold transition-colors"
        >
          {saved ? "已保存 ✓" : "保存"}
        </button>
      </div>
    </div>
  );
}

function Field({ label, value, placeholder, onChange }) {
  return (
    <div>
      <label className="block text-sm font-medium mb-2">{label}</label>
      <input
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm
                   text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
      />
    </div>
  );
}

function TimeField({ label, value, onChange }) {
  return (
    <div>
      <label className="block text-sm font-medium mb-2">{label}</label>
      <input
        type="time"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm
                   text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
      />
    </div>
  );
}
