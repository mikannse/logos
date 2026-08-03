"use client";

import { useState, useEffect, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Check, Loader2, AlertCircle, Server, Key, Cpu, Braces, Globe } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const PRESETS = [
  {
    label: "OpenAI",
    endpoint: "https://api.openai.com/v1",
    model: "gpt-4o-mini",
    provider: "openai",
  },
  {
    label: "Anthropic (via LiteLLM)",
    endpoint: "https://api.anthropic.com/v1",
    model: "claude-sonnet-4-20250514",
    provider: "anthropic",
  },
  {
    label: "DeepSeek V4",
    endpoint: "https://api.deepseek.com",
    model: "deepseek-v4-pro",
    provider: "deepseek",
  },
  {
    label: "LiteLLM Proxy",
    endpoint: "http://localhost:4000/v1",
    model: "gpt-4o-mini",
    provider: "litellm",
  },
  {
    label: "Ollama (本地)",
    endpoint: "http://localhost:11434/v1",
    model: "qwen2.5:7b",
    provider: "ollama",
  },
];

export default function SettingsPage() {
  const router = useRouter();
  const [endpoint, setEndpoint] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [provider, setProvider] = useState("");
  const [hasExistingKey, setHasExistingKey] = useState(false);
  const [hasExistingTavilyKey, setHasExistingTavilyKey] = useState(false);
  const [tavilyApiKey, setTavilyApiKey] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [status, setStatus] = useState<{ type: "success" | "error" | "info"; message: string } | null>(null);
  const [activePreset, setActivePreset] = useState<string | null>(null);

  // Load current config on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/config/llm`)
      .then((r) => r.json())
      .then((data) => {
        setEndpoint(data.endpoint || "");
        setModel(data.model || "");
        setProvider(data.provider || "");
        setHasExistingKey(data.has_api_key || false);
        setHasExistingTavilyKey(data.has_tavily_api_key || false);
      })
      .catch(() => {
        setStatus({ type: "error", message: "无法连接后端服务" });
      })
      .finally(() => setIsLoading(false));
  }, []);

  const applyPreset = (preset: typeof PRESETS[0]) => {
    setEndpoint(preset.endpoint);
    setModel(preset.model);
    setProvider(preset.provider);
    setActivePreset(preset.label);
    setStatus({ type: "info", message: `已选择 ${preset.label} 预设，填 API Key 后保存` });
  };

  const handleSave = async (e: FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setStatus(null);

    try {
      const res = await fetch(`${API_BASE}/api/config/llm`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint, api_key: apiKey, model, provider, tavily_api_key: tavilyApiKey }),
      });

      if (!res.ok) {
        // 透出后端校验 detail（如 "端口号无效"），避免误导用户检查服务是否运行
        const data = await res.json().catch(() => ({}));
        throw new Error((data as { detail?: string })?.detail || "保存失败");
      }

      setStatus({ type: "success", message: "配置已保存！" });
      setHasExistingKey(true);
      setApiKey(""); // Clear key field after save
      setHasExistingTavilyKey(true);
      setTavilyApiKey(""); // Clear Tavily key field after save
    } catch (err) {
      setStatus({
        type: "error",
        message:
          err instanceof Error ? err.message : "保存失败，请检查后端服务是否运行",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleTest = async () => {
    setIsTesting(true);
    setStatus(null);

    // 如果用户当前未输入 Key 但后端有已保存的 Key，用空字符串让后端使用已存配置
    const keyToSend = apiKey || (hasExistingKey ? "" : "test-key");

    try {
      const res = await fetch(`${API_BASE}/api/config/llm/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          endpoint,
          api_key: keyToSend,
          model,
          provider,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setStatus({ type: "error", message: data.detail || "连接失败" });
      } else {
        setStatus({ type: "success", message: data.message });
      }
    } catch {
      setStatus({ type: "error", message: "连接失败，请检查网络和端点地址" });
    } finally {
      setIsTesting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-6 h-6 animate-spin text-surface-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-8">
        <button
          onClick={() => router.back()}
          className="p-2 rounded-lg hover:bg-surface-muted hover:shadow-[var(--shadow-glow-sm)] transition-all duration-200 cursor-pointer"
          aria-label="返回"
        >
          <ArrowLeft className="w-5 h-5 text-surface-foreground" />
        </button>
        <div>
          <h1 className="text-xl font-bold text-surface-foreground font-heading">
            设置
          </h1>
          <p className="text-sm text-surface-muted-foreground">
            配置 AI 模型连接
          </p>
        </div>
      </div>

      {/* Presets */}
      <section className="mb-8">
        <h2 className="text-sm font-semibold text-surface-foreground mb-3 font-heading">
          快速配置
        </h2>
        <div className="grid grid-cols-2 gap-2">
          {PRESETS.map((p) => (
            <button
              key={p.label}
              onClick={() => applyPreset(p)}
              className={`text-left px-3 py-2.5 rounded-xl border text-sm transition-all duration-200 cursor-pointer ${
                activePreset === p.label
                  ? "border-brand-accent/60 bg-brand-accent/10 ring-1 ring-brand-accent/30 shadow-[var(--shadow-glow-sm)]"
                  : "border-border-default hover:border-surface-muted-foreground/50 hover:bg-surface-muted/40 bg-surface-card/80 hover:-translate-y-0.5"
              }`}
            >
              <div className="font-medium text-surface-foreground">{p.label}</div>
              <div className="text-[10px] text-surface-muted-foreground mt-0.5 truncate font-mono">
                {p.endpoint}
              </div>
            </button>
          ))}
        </div>
      </section>

      {/* Form */}
      <form onSubmit={handleSave} className="space-y-5">
        {/* Endpoint */}
        <div>
          <label className="flex items-center gap-1.5 text-sm font-medium text-surface-foreground mb-1.5">
            <Server className="w-4 h-4 text-brand-accent" />
            API 端点
          </label>
          <input
            type="url"
            value={endpoint}
            onChange={(e) => setEndpoint(e.target.value)}
            placeholder="https://api.openai.com/v1"
            className="w-full h-11 px-3.5 bg-surface-card/80 border border-border-default rounded-xl text-sm text-surface-foreground placeholder:text-surface-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-brand-accent/40 focus:border-brand-accent/50 transition-shadow duration-200"
            required
          />
          <p className="mt-1.5 text-[11px] text-surface-muted-foreground">
            兼容 OpenAI 格式的 API 端点（LiteLLM Proxy 通常为 http://localhost:4000/v1）
          </p>
        </div>

        {/* API Key */}
        <div>
          <label className="flex items-center gap-1.5 text-sm font-medium text-surface-foreground mb-1.5">
            <Key className="w-4 h-4 text-brand-accent" />
            API Key
          </label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={hasExistingKey ? "已配置（输入新 Key 覆盖）" : "输入 API Key..."}
            className="w-full h-11 px-3.5 bg-surface-card/80 border border-border-default rounded-xl text-sm text-surface-foreground placeholder:text-surface-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-brand-accent/40 focus:border-brand-accent/50 transition-shadow duration-200"
          />
          {hasExistingKey && !apiKey && (
            <p className="mt-1.5 text-[11px] text-success">✅ 已有 Key 配置，无需重复填写</p>
          )}
        </div>

        {/* Tavily API Key（全网搜索） */}
        <div>
          <label className="flex items-center gap-1.5 text-sm font-medium text-surface-foreground mb-1.5">
            <Globe className="w-4 h-4 text-brand-accent" />
            Tavily API Key
          </label>
          <input
            type="password"
            value={tavilyApiKey}
            onChange={(e) => setTavilyApiKey(e.target.value)}
            placeholder={hasExistingTavilyKey ? "已配置（输入新 Key 覆盖）" : "输入 Tavily API Key..."}
            className="w-full h-11 px-3.5 bg-surface-card/80 border border-border-default rounded-xl text-sm text-surface-foreground placeholder:text-surface-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-brand-accent/40 focus:border-brand-accent/50 transition-shadow duration-200"
          />
          {hasExistingTavilyKey && !tavilyApiKey && (
            <p className="mt-1.5 text-[11px] text-success">✅ 已有 Tavily Key 配置，无需重复填写</p>
          )}
          <p className="mt-1.5 text-[11px] text-surface-muted-foreground">
            全网搜索用（申请自 tavily.com），用于图谱与时间轴的 Web 内容丰富，可留空
          </p>
        </div>

        {/* Model */}
        <div>
          <label className="flex items-center gap-1.5 text-sm font-medium text-surface-foreground mb-1.5">
            <Cpu className="w-4 h-4 text-brand-accent" />
            模型名称
          </label>
          <input
            type="text"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="gpt-4o-mini"
            className="w-full h-11 px-3.5 bg-surface-card/80 border border-border-default rounded-xl text-sm text-surface-foreground placeholder:text-surface-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-brand-accent/40 focus:border-brand-accent/50 transition-shadow duration-200"
            required
          />
          <p className="mt-1.5 text-[11px] text-surface-muted-foreground">
            常用模型：gpt-4o-mini / claude-sonnet-4-20250514 / qwen2.5:7b
          </p>
        </div>

        {/* Status */}
        {status && (
          <div
            className={`flex items-start gap-2 p-3 rounded-xl border text-sm ${
              status.type === "success"
                ? "bg-success/10 border-success/30 text-success"
                : status.type === "error"
                  ? "bg-destructive/10 border-destructive/30 text-destructive"
                  : "bg-surface-muted border-border-default text-surface-foreground"
            }`}
          >
            {status.type === "success" ? (
              <Check className="w-4 h-4 mt-0.5 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            )}
            <span>{status.message}</span>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={isSaving}
            className="h-11 px-5 bg-brand-accent text-surface-card rounded-xl text-sm font-medium hover:bg-brand-accent-strong hover:shadow-[var(--shadow-glow-sm)] active:scale-[0.98] disabled:opacity-50 transition-all duration-200 cursor-pointer inline-flex items-center gap-1.5"
          >
            {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
            保存配置
          </button>
          <button
            type="button"
            onClick={handleTest}
            disabled={isTesting || (!apiKey && !hasExistingKey)}
            className="h-11 px-5 border border-border-default text-surface-foreground rounded-xl text-sm font-medium hover:bg-surface-muted disabled:opacity-50 transition-colors duration-200 cursor-pointer inline-flex items-center gap-1.5"
          >
            {isTesting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Braces className="w-4 h-4" />}
            测试连接
          </button>
        </div>
      </form>
    </div>
  );
}
