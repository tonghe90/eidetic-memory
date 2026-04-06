import React, { useEffect, useState } from "react";

export default function Settings() {
  const [form, setForm] = useState({
    llm_provider: "claude",
    anthropic_api_key: "",
    openai_api_key: "",
    ollama_base_url: "http://127.0.0.1:11434",
    ollama_model: "qwen3.5-27b",
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
          ollama_model: data.ollama_model || "qwen3.5-27b",
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
              placeholder="qwen3.5-27b"
              onChange={(v) => setForm((f) => ({ ...f, ollama_model: v }))}
            />
            <p className="text-xs text-gray-400 -mt-3">
              例如填写你本地 Ollama 已拉取的模型名；保存后，分类、搜索回答与摄取都会走本地模型。
            </p>
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
