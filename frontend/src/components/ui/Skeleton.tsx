import { clsx } from "clsx";

export default function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={clsx(
        "animate-pulse-subtle rounded-lg bg-surface-muted",
        className
      )}
      {...props}
    />
  );
}
