"use client";

import { ExternalLink, Globe, FileText } from "lucide-react";

interface SourceLinkProps {
  url?: string;
  name?: string;
  evidence?: string;
}

export default function SourceLink({ url, name, evidence }: SourceLinkProps) {
  if (!url && !name && !evidence) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-surface-muted-foreground">
        <FileText className="w-3 h-3" />
        来源未知
      </span>
    );
  }

  const displayName =
    name ||
    (url
      ? new URL(url).hostname.replace("www.", "").split(".")[0]
      : "未知来源");

  return (
    <span className="inline-flex items-center gap-1">
      <Globe className="w-3 h-3 text-surface-muted-foreground" />
      {url ? (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-brand-accent hover:underline inline-flex items-center gap-0.5"
          title={evidence || url}
        >
          {displayName}
          <ExternalLink className="w-2.5 h-2.5" />
        </a>
      ) : (
        <span className="text-xs text-surface-muted-foreground">{displayName}</span>
      )}
    </span>
  );
}
