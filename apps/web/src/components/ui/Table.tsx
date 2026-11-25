import React from "react";
import { cn } from "@/lib/cn";

/** Edge-to-edge table for a Card with padded={false}: 12px muted head on a tinted row, 14px cells, row dividers. */
export function Table({ className, children, ...rest }: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className="overflow-x-auto">
      <table className={cn("w-full text-body text-ink border-collapse", className)} {...rest}>{children}</table>
    </div>
  );
}

export function THead({ children }: { children: React.ReactNode }) {
  return <thead className="bg-surface-2 border-y border-line">{children}</thead>;
}

export function Th({ className, align = "left", ...rest }: React.ThHTMLAttributes<HTMLTableCellElement> & { align?: "left" | "right" | "center" }) {
  return <th scope="col" className={cn("px-5 h-10 text-caption font-medium text-muted whitespace-nowrap",
    align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left", className)} {...rest} />;
}

export function Tr({ className, ...rest }: React.HTMLAttributes<HTMLTableRowElement> & { [data: `data-${string}`]: string | undefined }) {
  return <tr className={cn("border-b border-line-soft last:border-b-0", className)} {...rest} />;
}

export function Td({ className, align = "left", ...rest }: React.TdHTMLAttributes<HTMLTableCellElement> & { align?: "left" | "right" | "center" }) {
  return <td className={cn("px-5 py-3 align-middle",
    align === "right" ? "text-right tabular" : align === "center" ? "text-center" : "text-left", className)} {...rest} />;
}
