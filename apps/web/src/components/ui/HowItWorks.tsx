"use client";

/** A collapsible "How this works" card: a title and numbered steps from the locale files
 *  (`howto.<topic>.title`, `howto.<topic>.1` … `howto.<topic>.<steps>`). Closed by default. */
import React from "react";
import { HelpCircle, ChevronDown } from "lucide-react";
import { useLanguage } from "@/lib/LanguageContext";
import { cn } from "@/lib/cn";

export function HowItWorks({ topic, steps, className, open = false }: { topic: string; steps: number; className?: string; open?: boolean }) {
  const { t } = useLanguage();
  return (
    <details open={open} className={cn("group bg-brand-soft border border-brand-line rounded-card", className)} data-testid={`howto-${topic}`}>
      <summary className="px-4 py-2.5 cursor-pointer list-none flex items-center justify-between gap-2 text-label font-semibold text-ink">
        <span className="flex items-center gap-2"><HelpCircle className="w-4 h-4 text-brand" />{t(`howto.${topic}.title`)}</span>
        <ChevronDown className="w-4 h-4 text-muted transition-transform group-open:rotate-180" />
      </summary>
      <ol className="px-4 pb-3 pl-9 list-decimal space-y-1 text-label text-ink-soft">
        {Array.from({ length: steps }, (_, i) => <li key={i}>{t(`howto.${topic}.${i + 1}`)}</li>)}
      </ol>
    </details>
  );
}
