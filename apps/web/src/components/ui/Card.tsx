import React from "react";
import { cn } from "@/lib/cn";

type DivProps = React.HTMLAttributes<HTMLElement> & { as?: "div" | "section" | "article" | "aside"; [data: `data-${string}`]: string | undefined };

/** White panel: 12px corners, 1px line, soft shadow. `padded={false}` for tables that run edge to edge. */
export function Card({ as: Tag = "section", padded = true, className, children, ...rest }: DivProps & { padded?: boolean }) {
  return (
    <Tag className={cn("bg-surface border border-line rounded-card shadow-card", padded && "p-5", className)} {...rest}>
      {children}
    </Tag>
  );
}

/** Card title row. Use inside a padded Card, or with `className="px-5 pt-5"` above an edge-to-edge table. */
export function CardHeader({ title, subtitle, actions, className, level = 2 }: {
  title: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode; className?: string; level?: 2 | 3;
}) {
  const H = level === 2 ? "h2" : "h3";
  return (
    <div className={cn("flex flex-wrap items-start justify-between gap-3 mb-4", className)}>
      <div className="min-w-0">
        <H className="text-heading font-semibold text-ink">{title}</H>
        {subtitle && <p className="mt-0.5 text-label text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
    </div>
  );
}
