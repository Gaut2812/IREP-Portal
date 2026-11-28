import React from "react";
import { cn } from "@/lib/cn";
import type { Tone } from "./Metrics";

/* ---------- Badge ---------- */

const BADGE_TONE: Record<Tone | "info" | "violet", string> = {
  neutral: "bg-line-soft text-ink-soft",
  brand: "bg-brand-soft text-brand",
  info: "bg-info-soft text-info",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  danger: "bg-danger-soft text-danger",
  violet: "bg-violet-soft text-violet",
};

export function Badge({ tone = "neutral", className, children, ...rest }: React.HTMLAttributes<HTMLSpanElement> & {
  tone?: keyof typeof BADGE_TONE; [data: `data-${string}`]: string | undefined;
}) {
  return (
    <span className={cn("inline-flex items-center gap-1 px-2 py-px rounded-full text-caption font-medium whitespace-nowrap", BADGE_TONE[tone], className)} {...rest}>
      {children}
    </span>
  );
}

/* ---------- Button ---------- */

const BTN_VARIANT = {
  primary: "bg-brand text-white hover:bg-brand-hover border border-brand",
  secondary: "bg-surface text-ink border border-line hover:bg-surface-2",
  ghost: "bg-transparent text-ink-soft border border-transparent hover:bg-line-soft",
  danger: "bg-danger text-white border border-danger hover:opacity-90",
} as const;
const BTN_SIZE = { sm: "h-8 px-3 text-label", md: "h-9 px-4 text-body" } as const;

export function buttonClass(variant: keyof typeof BTN_VARIANT = "primary", size: keyof typeof BTN_SIZE = "md", className?: string) {
  return cn("inline-flex items-center justify-center gap-1.5 rounded-tile font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none",
    BTN_VARIANT[variant], BTN_SIZE[size], className);
}

export function Button({ variant = "primary", size = "md", className, type = "button", ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof BTN_VARIANT; size?: keyof typeof BTN_SIZE; [data: `data-${string}`]: string | undefined;
}) {
  return <button type={type} className={buttonClass(variant, size, className)} {...rest} />;
}

/* ---------- Form fields ---------- */

export const inputClass =
  "h-9 w-full px-3 bg-surface border border-line rounded-tile text-body text-ink placeholder:text-subtle " +
  "focus:outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 disabled:bg-surface-2";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...rest }, ref) { return <input ref={ref} className={cn(inputClass, className)} {...rest} />; });

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, ...rest }, ref) { return <select ref={ref} className={cn(inputClass, "w-auto pr-8", className)} {...rest} />; });

export function Field({ label, hint, children, className }: { label: React.ReactNode; hint?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <label className={cn("block space-y-1.5", className)}>
      <span className="block text-label font-medium text-ink-soft">{label}</span>
      {children}
      {hint && <span className="block text-caption text-muted">{hint}</span>}
    </label>
  );
}

/* ---------- Tabs ---------- */

export function Tabs<T extends string>({ value, onChange, items, className, label }: {
  value: T; onChange: (v: T) => void; items: { value: T; label: React.ReactNode; testId?: string }[]; className?: string; label?: string;
}) {
  return (
    <div role="tablist" aria-label={label} className={cn("inline-flex p-1 gap-1 bg-line-soft rounded-tile", className)}>
      {items.map((it) => (
        <button key={it.value} type="button" role="tab" aria-selected={value === it.value} data-testid={it.testId}
          onClick={() => onChange(it.value)}
          className={cn("h-8 px-3 rounded-md text-label font-medium transition-colors",
            value === it.value ? "bg-surface text-ink shadow-card" : "text-muted hover:text-ink")}>
          {it.label}
        </button>
      ))}
    </div>
  );
}

/* ---------- Empty state ---------- */

export function EmptyState({ title, hint, icon, action, className }: {
  title: React.ReactNode; hint?: React.ReactNode; icon?: React.ReactNode; action?: React.ReactNode; className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center text-center py-10 px-4", className)}>
      {icon && <div className="mb-3 text-subtle">{icon}</div>}
      <div className="text-body font-medium text-ink">{title}</div>
      {hint && <div className="mt-1 text-label text-muted max-w-sm">{hint}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
