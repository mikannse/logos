// 常量定义

export const SITE_NAME = "Logos";
export const SITE_TAGLINE = "给你的好奇心装一张知识地图";
export const SITE_DESCRIPTION = "搜一个名词，自动构建关系图谱与演化时间轴";

// API
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// 图谱
export const GRAPH_MAX_DEPTH = 3;
export const GRAPH_DEFAULT_DEPTH = 1;
export const GRAPH_NODE_LIMIT = 200;
export const GRAPH_ANIMATION_DURATION = 300;

// 搜索
export const SEARCH_DEBOUNCE_MS = 200;
export const SEARCH_MIN_LENGTH = 2;

// 热门搜索推荐
export const POPULAR_SEARCHES = ["爱因斯坦", "区块链", "CRISPR", "神经网络", "量子计算"];

// 关系类型颜色映射
export const EDGE_COLORS: Record<string, string> = {
  influence: "#DC2626",      // 红色 - 影响
  affiliation: "#2563EB",    // 蓝色 - 隶属
  creation: "#16A34A",       // 绿色 - 创作
  default: "#64748B",        // 灰色 - 其他
};

// 置信度等级
export const CONFIDENCE_LEVELS = {
  HIGH: { label: "高", min: 0.8, color: "#16A34A" },
  MEDIUM: { label: "中", min: 0.5, color: "#D97706" },
  LOW: { label: "低", min: 0.0, color: "#DC2626" },
} as const;
