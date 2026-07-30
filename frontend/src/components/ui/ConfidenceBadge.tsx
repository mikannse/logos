"use client";

import { Shield, ShieldCheck, AlertTriangle, HelpCircle } from "lucide-react";

interface ConfidenceBadgeProps {
  confidence: number;
  showLabel?: boolean;
  size?: "sm" | "md";
}

const LEVELS = [
  { min: 0.8, label: "高", color: "text-success", bg: "bg-success/10", icon: ShieldCheck },
  { min: 0.5, label: "中", color: "text-warning", bg: "bg-warning/10", icon: AlertTriangle },
  { min: 0, label: "低", color: "text-destructive", bg: "bg-destructive/10", icon: HelpCircle },
] as const;

export default function ConfidenceBadge({
  confidence,
  showLabel = true,
  size = "sm",
}: ConfidenceBadgeProps) {
  const level = LEVELS.find((l) => confidence >= l.min) || LEVELS[2];
  const Icon = level.icon;
  const textSize = size === "sm" ? "text-[10px]" : "text-xs";
  const iconSize = size === "sm" ? "w-3 h-3" : "w-3.5 h-3.5";

  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full ${level.bg} ${level.color} ${textSize} font-medium`}
      title={`置信度: ${level.label} (${Math.round(confidence * 100)}%)`}
    >
      <Icon className={iconSize} />
      {showLabel && (
        <span>
          {level.label} {Math.round(confidence * 100)}%
        </span>
      )}
    </span>
  );
}
