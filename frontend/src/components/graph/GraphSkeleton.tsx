import Skeleton from "@/components/ui/Skeleton";

export default function GraphSkeleton() {
  return (
    <div className="relative w-full h-full min-h-[400px] flex items-center justify-center overflow-hidden">
      {/* Simulated graph skeleton */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="relative w-72 h-72">
          {/* Orbit rings */}
          <div className="absolute inset-0 rounded-full border border-border-default animate-spin-slow" />
          <div className="absolute inset-4 rounded-full border border-border-default/60" />
          <div className="absolute inset-8 rounded-full border border-border-default/40" />

          {/* Center node */}
          <Skeleton className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-16 h-16 rounded-full" />
          {/* Surrounding nodes */}
          {[
            { top: "0%", left: "50%" },
            { top: "15%", left: "8%" },
            { top: "15%", left: "88%" },
            { top: "40%", left: "-2%" },
            { top: "40%", left: "98%" },
            { top: "78%", left: "18%" },
            { top: "78%", left: "78%" },
          ].map((pos, i) => (
            <Skeleton
              key={i}
              className="absolute w-10 h-10 rounded-full"
              style={{ top: pos.top, left: pos.left }}
            />
          ))}
        </div>
      </div>

      {/* Loading label */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-2 rounded-full border border-border-default bg-surface-card/80 px-4 py-1.5 text-sm text-surface-muted-foreground backdrop-blur-md">
        <span className="h-3.5 w-3.5 rounded-full border-2 border-brand-accent border-t-transparent animate-spin" />
        正在构建关系图谱…
      </div>
    </div>
  );
}
