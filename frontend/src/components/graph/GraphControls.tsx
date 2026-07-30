"use client";

import { ZoomIn, ZoomOut, Maximize2 } from "lucide-react";

interface GraphControlsProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  onFullscreen?: () => void;
}

export default function GraphControls({
  onZoomIn,
  onZoomOut,
  onReset,
  onFullscreen,
}: GraphControlsProps) {
  return (
    <div className="flex flex-col gap-1">
      <button
        onClick={onZoomIn}
        className="p-2 bg-surface-card border border-border-default rounded-t-lg text-surface-muted-foreground hover:text-surface-foreground hover:bg-surface-muted transition-colors cursor-pointer"
        aria-label="放大"
        title="放大"
      >
        <ZoomIn className="w-4 h-4" />
      </button>
      <button
        onClick={onZoomOut}
        className="p-2 bg-surface-card border-x border-border-default text-surface-muted-foreground hover:text-surface-foreground hover:bg-surface-muted transition-colors cursor-pointer"
        aria-label="缩小"
        title="缩小"
      >
        <ZoomOut className="w-4 h-4" />
      </button>
      <button
        onClick={onReset}
        className="p-2 bg-surface-card border border-border-default text-surface-muted-foreground hover:text-surface-foreground hover:bg-surface-muted transition-colors cursor-pointer"
        aria-label="重置视图"
        title="重置视图"
      >
        <Maximize2 className="w-4 h-4" />
      </button>
    </div>
  );
}
