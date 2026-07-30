import Skeleton from "@/components/ui/Skeleton";

export default function GraphSkeleton() {
  return (
    <div className="relative w-full h-full min-h-[400px] flex items-center justify-center">
      {/* Simulated graph skeleton */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="relative w-64 h-64">
          {/* Center node */}
          <Skeleton className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-16 h-16 rounded-full" />
          {/* Surrounding nodes */}
          {[
            { top: "10%", left: "50%" },
            { top: "25%", left: "15%" },
            { top: "25%", left: "80%" },
            { top: "55%", left: "5%" },
            { top: "55%", left: "90%" },
            { top: "80%", left: "30%" },
            { top: "80%", left: "65%" },
          ].map((pos, i) => (
            <Skeleton
              key={i}
              className="absolute w-10 h-10 rounded-full"
              style={{ top: pos.top, left: pos.left }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
