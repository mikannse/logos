// 图谱类型定义

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

export type NodeType = "person" | "entity" | "event";
export type ConfidenceLevel = "high" | "medium" | "low";

// D3 力导向图扩展类型
export interface SimulationNode extends GraphNode {
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
}

export interface SimulationLink {
  source: string | SimulationNode;
  target: string | SimulationNode;
  type: string;
  confidence: number;
  source_url: string;
  evidence?: string;
}
