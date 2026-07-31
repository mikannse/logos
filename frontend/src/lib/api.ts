// API 客户端封装
// 所有 API 调用走统一客户端
// 字段：后端 snake_case → 前端保留 snake_case（不做转换）

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  status: number;
  details: Record<string, unknown>;

  // FastAPI 错误可能返回 {detail: ...}，Logos 风格返回 {error: {...}}。
  // 统一兼容，避免访问 undefined 抛 TypeError 掩盖真实错误。
  constructor(response: {
    error?: { code?: string; message?: string; status?: number; details?: Record<string, unknown> };
    detail?: unknown;
    status?: number;
  }) {
    super(
      response?.error?.message ||
      (typeof response?.detail === "string" ? response.detail : "请求失败")
    );
    this.code = response?.error?.code || "unknown";
    this.status = response?.error?.status || response?.status || 0;
    this.details = response?.error?.details || {};
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body);
  }

  return res.json();
}

export interface SearchResult {
  id: string;
  name: string;
  type: string;
  confidence: number;
  summary?: string;
}

export interface DisambiguationGroup {
  id: string;
  label: string;
  label_en: string;
  type_label: string;
  confidence: number;
  summary: string;
}

export interface SearchResponse {
  results: SearchResult[];
  query: string;
  total: number;
  needs_disambiguation: boolean;
  disambiguation_groups: DisambiguationGroup[];
}

export interface GraphNode {
  id: string;
  label: string;
  type: "person" | "entity" | "event";
  confidence: number;
  summary?: string;
  image_url?: string;
  year?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  confidence: number;
  source_url: string;
  evidence?: string;
}

export interface GraphResponse {
  center: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  depth: number;
  has_more: boolean;
}

export interface Milestone {
  year: number;
  title: string;
  description: string;
  source_url: string;
  confidence: number;
}

export interface TimelineResponse {
  noun_id: string;
  milestones: Milestone[];
  total: number;
}

export async function searchNouns(query: string): Promise<SearchResponse> {
  return request<SearchResponse>(
    `/api/nouns?q=${encodeURIComponent(query)}`
  );
}

export async function fetchGraph(
  nounId: string,
  depth = 1
): Promise<GraphResponse> {
  return request<GraphResponse>(
    `/api/nouns/${nounId}/graph?depth=${depth}`
  );
}

export async function fetchTimeline(
  nounId: string
): Promise<TimelineResponse> {
  return request<TimelineResponse>(`/api/nouns/${nounId}/timeline`);
}

export async function fetchNoun(nounId: string): Promise<SearchResult> {
  return request<SearchResult>(`/api/nouns/${nounId}`);
}

export async function healthCheck(): Promise<{ status: string }> {
  return request<{ status: string }>("/api/health");
}
