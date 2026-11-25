import React from "react";
import { cn } from "@/lib/cn";

/** Page title (the screen's only h1), optional one-line subtitle and actions on the right. AppShell renders it. */
export function PageHeader({ title, subtitle, actions, className }: {
  title: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode; className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-end justify-between gap-3 mb-6", className)}>
      <div className="min-w-0">
        <h1 className="text-title font-semibold text-ink">{title}</h1>
        {subtitle && <p className="mt-1 text-body text-muted max-w-3xl">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
    </div>
  );
}
