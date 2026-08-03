"use client";

import { ChevronRight, Home } from "lucide-react";

interface BreadcrumbItem {
  id: string;
  label: string;
  type?: string;
}

interface BreadcrumbNavProps {
  items: BreadcrumbItem[];
  onNavigate: (item: BreadcrumbItem, index: number) => void;
}

export default function BreadcrumbNav({ items, onNavigate }: BreadcrumbNavProps) {
  if (items.length === 0) return null;

  return (
    <nav
      className="flex items-center gap-1 text-sm overflow-x-auto pb-1 scrollbar-thin"
      aria-label="探索路径"
      style={{ scrollbarWidth: "thin" }}
    >
      <button
        onClick={() => onNavigate(items[0], 0)}
        className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-surface-muted-foreground hover:text-surface-foreground hover:bg-surface-muted/70 hover:shadow-[var(--shadow-glow-sm)] transition-all duration-200 shrink-0 cursor-pointer"
        aria-label="返回起始"
      >
        <Home className="w-3.5 h-3.5" />
      </button>

      {items.map((item, i) => (
        <div key={item.id} className="flex items-center gap-1 shrink-0">
          <ChevronRight className="w-3 h-3 text-surface-muted-foreground/60" />
          <button
            onClick={() => onNavigate(item, i)}
            className={`px-2.5 py-1 rounded-lg transition-all duration-200 cursor-pointer ${
              i === items.length - 1
                ? "text-surface-foreground font-medium bg-surface-muted/80 border border-border-default"
                : "text-surface-muted-foreground hover:text-surface-foreground hover:bg-surface-muted/50"
            }`}
          >
            <span className="truncate max-w-[120px] inline-block align-middle">
              {item.label}
            </span>
            {item.type && (
              <span className="ml-1 text-[10px] text-surface-muted-foreground">
                ({item.type})
              </span>
            )}
          </button>
        </div>
      ))}
    </nav>
  );
}
