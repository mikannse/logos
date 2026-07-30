import { FileSearch } from "lucide-react";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export default function EmptyState({
  icon,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="text-surface-muted-foreground mb-4">
        {icon || <FileSearch className="w-12 h-12" />}
      </div>
      <h3 className="text-lg font-semibold text-surface-foreground">{title}</h3>
      {description && (
        <p className="mt-2 text-sm text-surface-muted-foreground max-w-sm">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
