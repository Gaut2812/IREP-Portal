import React from "react";
import { cn } from "@/lib/cn";

export type Tone = "neutral" | "brand" | "success" | "warning" | "danger";

const VALUE_TONE: Record<Tone, string> = {
  neutral: "text-ink", brand: "text-brand", success: "text-success", warning: "text-warning", danger: "text-danger",
};
const FILL_TONE: Record<Tone, string> = {
  neutral: "bg-subtle", brand: "bg-brand", success: "bg-success-fill", warning: "bg-warning-fill", danger: "bg-danger-fill",
};

/** Green when up, red when down, neutral when unknown or flat. */
export function deltaTone(d: number | null | undefined): Tone {
  if (d === null || d === undefined || d === 0) return "neutral";
  return d > 0 ? "success" : "danger";
}

/** KPI card: label, big number, one line of context. */
export function StatTile({ label, value, hint, tone = "neutral", valueTestId, className, children, ...rest }: {
  label: React.ReactNode; value?: React.ReactNode; hint?: React.ReactNode; tone?: Tone; valueTestId?: string;
  className?: string; children?: React.ReactNode; [data: `data-${string}`]: string | undefined;
}) {
  return (
    <div className={cn("bg-surface border border-line rounded-card shadow-card p-5 min-w-0", className)} {...rest}>
      <div className="text-label font-medium text-muted">{label}</div>
      {value !== undefined && (
        <div className={cn("mt-2 text-kpi font-semibold tabular", VALUE_TONE[tone])} data-testid={valueTestId}>{value}</div>
      )}
      {children && <div className="mt-3">{children}</div>}
      {hint && <div className="mt-1.5 text-label text-muted">{hint}</div>}
    </div>
  );
}

/** Thin progress bar, 0–100. */
export function ProgressBar({ value, tone = "brand", className, label }: { value: number; tone?: Tone; className?: string; label?: string }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className={cn("h-1.5 rounded-full bg-line-soft overflow-hidden", className)} role="progressbar"
      aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)} aria-label={label}>
      <div className={cn("h-full rounded-full", FILL_TONE[tone])} style={{ width: `${pct}%` }} />
    </div>
  );
}

/** Small tile with a label, a value and a bar (the score breakdown boxes). */
export function MetricBar({ label, value, display, tone = "brand", className }: {
  label: React.ReactNode; value: number; display?: React.ReactNode; tone?: Tone; className?: string;
}) {
  return (
    <div className={cn("flex flex-col bg-surface-2 border border-line rounded-tile p-4 min-w-0", className)}>
      {/* long (Tamil) labels wrap to two lines; value and bar stay aligned across the row */}
      <div className="flex-1 text-label text-muted line-clamp-2" title={typeof label === "string" ? label : undefined}>{label}</div>
      <div className="mt-1 text-heading font-semibold text-ink tabular">{display ?? value}</div>
      <ProgressBar value={value} tone={tone} className="mt-3" label={typeof label === "string" ? label : undefined} />
    </div>
  );
}

export interface Segment { key: string; value: number; tone: Tone; label: string }

/** Stacked bar of parts of a whole (e.g. readiness bands), with an optional legend. */
export function DistributionBar({ segments, legend = false, className, ...rest }: {
  segments: Segment[]; legend?: boolean; className?: string; [data: `data-${string}`]: string | undefined;
}) {
  const total = segments.reduce((n, s) => n + s.value, 0);
  return (
    <div className={cn("min-w-0", className)} {...rest}>
      <div className="flex h-2 rounded-full overflow-hidden bg-line-soft gap-px">
        {total > 0 && segments.filter((s) => s.value > 0).map((s) => (
          <div key={s.key} className={FILL_TONE[s.tone]} style={{ width: `${(100 * s.value) / total}%` }} title={`${s.label}: ${s.value}`} />
        ))}
      </div>
      {legend && (
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-caption text-muted">
          {segments.map((s) => (
            <span key={s.key} className="inline-flex items-center gap-1.5">
              <span className={cn("w-2 h-2 rounded-full", FILL_TONE[s.tone])} aria-hidden />
              {s.label} <span className="text-ink font-medium tabular">{s.value}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
