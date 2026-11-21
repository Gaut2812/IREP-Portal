"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLanguage } from "@/lib/LanguageContext";

/** Screen 48 sub-navigation: trail, consent, data requests. */
export function AuditTabs() {
  const { t } = useLanguage();
  const path = usePathname();
  const tabs = [
    { href: "/admin/audit", label: t("admin_audit.tab_trail") },
    { href: "/admin/audit/consent", label: t("admin_audit.tab_consent") },
    { href: "/admin/audit/requests", label: t("admin_audit.tab_requests") },
  ];
  return (
    <nav className="flex gap-1 border-b border-[#E2E8F0]" aria-label={t("admin_audit.tabs_label")}>
      {tabs.map((tab) => {
        const on = path === tab.href;
        return (
          <Link key={tab.href} href={tab.href} aria-current={on ? "page" : undefined}
            className={`px-3 py-2 text-xs font-bold border-b-2 -mb-px ${on ? "border-[#2B5CD0] text-[#2B5CD0]" : "border-transparent text-[#64748B] hover:text-[#0F1F3A]"}`}>
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}

/** Download a protected file through fetch (the API needs the bearer token). */
export async function downloadWithAuth(url: string, headers: Record<string, string>, filename: string): Promise<void> {
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error(String(res.status));
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}
