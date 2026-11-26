"use client";

/** Screen 44 · Notification centre (every role, opened from the bell). */
import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { BellRing, CheckCheck, Inbox, Moon } from "lucide-react";

interface Item { id: string; kind: string; title: string; body: string | null; link: string | null; created_at: string | null; read: boolean }
interface Page { items: Item[]; unread: number; kinds: string[]; next_before: string | null }
interface Prefs { in_app: boolean; email_enabled: boolean; sms_enabled: boolean; push_enabled: boolean; quiet_start_hour: number | null; quiet_end_hour: number | null; language: "en" | "ta" }

const HOURS = Array.from({ length: 24 }, (_, h) => h);

export default function NotificationCentrePage() {
  const { t, language, setLanguage } = useLanguage();
  const [items, setItems] = useState<Item[]>([]);
  const [kinds, setKinds] = useState<string[]>([]);
  const [unread, setUnread] = useState(0);
  const [next, setNext] = useState<string | null>(null);
  const [kind, setKind] = useState("");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const kindLabel = (k: string) => {
    const label = t(`notifications.kinds.${k}`);
    return label.startsWith("notifications.kinds.") ? k : label;
  };

  const query = useCallback((before?: string | null) => {
    const q = new URLSearchParams({ lang: language, limit: "20" });
    if (kind) q.set("kind", kind);
    if (unreadOnly) q.set("unread_only", "true");
    if (before) q.set("before", before);
    return q.toString();
  }, [kind, language, unreadOnly]);

  const load = useCallback(async () => {
    try {
      const page = await fetchApi<Page>(`/notifications?${query()}`);
      setItems(page.items);
      setKinds((k) => (page.kinds.length ? page.kinds : k));
      setUnread(page.unread);
      setNext(page.next_before);
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("notifications.load_error"));
    }
  }, [query, t]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    // one language per user for screens and messages: start the form from the language on screen, so
    // saving quiet hours or channels never flips the page (the stored value can lag, e.g. Tamil chosen before sign-in)
    fetchApi<Prefs>("/notifications/preferences").then((p) => setPrefs({ ...p, language })).catch(() => setError(t("notifications.load_error")));
  }, [t, language]);

  const more = async () => {
    if (!next) return;
    const page = await fetchApi<Page>(`/notifications?${query(next)}`);
    setItems((cur) => [...cur, ...page.items]);
    setNext(page.next_before);
  };

  const markOne = async (it: Item) => {
    if (it.read) return;
    await fetchApi(`/notifications/${it.id}/read`, { method: "POST" });
    setItems((cur) => cur.map((x) => (x.id === it.id ? { ...x, read: true } : x)));
    setUnread((u) => Math.max(0, u - 1));
  };

  const markAll = async () => {
    await fetchApi("/notifications/read-all", { method: "POST" });
    await load();
  };

  const savePrefs = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prefs) return;
    setSaved(false);
    if ((prefs.quiet_start_hour === null) !== (prefs.quiet_end_hour === null)) { setError(t("notifications.err_quiet")); return; }
    try {
      const out = await fetchApi<Prefs>("/notifications/preferences", { method: "PUT", body: JSON.stringify(prefs) });
      setPrefs(out);
      if (out.language !== language) setLanguage(out.language, false);
      setSaved(true);
      setError("");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : t("notifications.save_error"));
    }
  };

  const hourSelect = (value: number | null, onChange: (v: number | null) => void, testid: string, label: string) => (
    <label className="text-caption font-semibold text-ink">{label}
      <select value={value === null ? "" : String(value)} data-testid={testid} onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        className="mt-1 w-full px-2 py-1.5 border border-line rounded-tile text-xs font-normal bg-white">
        <option value="">{t("notifications.off")}</option>
        {HOURS.map((h) => <option key={h} value={h}>{String(h).padStart(2, "0")}:00</option>)}
      </select>
    </label>
  );
  const toggle = (key: "email_enabled" | "sms_enabled" | "push_enabled", label: string) => prefs && (
    <label className="flex items-center justify-between text-xs py-1">
      <span>{label}</span>
      <input type="checkbox" checked={prefs[key]} data-testid={`pref-${key}`} onChange={(e) => setPrefs({ ...prefs, [key]: e.target.checked })} />
    </label>
  );

  return (
    <RoleGuard allowedRoles={["student", "trainer", "college", "parent", "admin"]}>
      <AppShell pageTitle={t("notifications.title")}>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 max-w-6xl">
          <section className="lg:col-span-2 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <select value={kind} onChange={(e) => setKind(e.target.value)} data-testid="filter-kind" aria-label={t("notifications.filter_kind")}
                className="px-2.5 py-1.5 border border-line rounded-tile text-xs bg-white">
                <option value="">{t("notifications.all_kinds")}</option>
                {kinds.map((k) => <option key={k} value={k}>{kindLabel(k)}</option>)}
              </select>
              <label className="flex items-center gap-1.5 text-xs"><input type="checkbox" checked={unreadOnly} data-testid="filter-unread" onChange={(e) => setUnreadOnly(e.target.checked)} />{t("notifications.unread_only")}</label>
              <span className="text-xs text-muted" data-testid="unread-count">{unread} {t("notifications.unread")}</span>
              <button type="button" onClick={markAll} data-testid="page-mark-all" className="ml-auto flex items-center gap-1 text-xs font-semibold text-brand"><CheckCheck className="w-3.5 h-3.5" />{t("notifications.mark_all_read")}</button>
            </div>
            {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
            <ul className="bg-white rounded-card border border-line divide-y divide-line-soft" data-testid="notification-list">
              {items.length === 0 && <li className="p-6 text-center text-xs text-muted flex flex-col items-center gap-1.5"><Inbox className="w-5 h-5 text-subtle" />{t("notifications.empty")}</li>}
              {items.map((it) => {
                const content = (
                  <div className={`px-4 py-3 ${it.read ? "" : "bg-brand-soft"}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="text-xs font-semibold text-ink">{it.title}</div>
                      <span className="text-caption text-muted whitespace-nowrap">{it.created_at?.slice(0, 16).replace("T", " ")}</span>
                    </div>
                    {it.body && <div className="text-caption text-muted mt-0.5">{it.body}</div>}
                    <span className="text-caption text-subtle" data-testid="notif-kind">{kindLabel(it.kind)}</span>
                  </div>
                );
                return (
                  <li key={it.id} data-testid="notification-item" data-read={it.read ? "true" : "false"}>
                    {it.link ? <Link href={it.link} onClick={() => markOne(it)} className="block hover:bg-surface-2">{content}</Link>
                      : <button type="button" onClick={() => markOne(it)} className="block w-full text-left hover:bg-surface-2">{content}</button>}
                  </li>
                );
              })}
            </ul>
            {next && <button type="button" onClick={more} data-testid="load-more" className="w-full py-2 border border-line-strong rounded-tile text-xs font-semibold">{t("notifications.load_more")}</button>}
          </section>

          <form onSubmit={savePrefs} className="bg-white rounded-card border border-line p-4 space-y-3 h-fit" data-testid="prefs-form">
            <h2 className="text-sm font-semibold text-ink flex items-center gap-2"><BellRing className="w-4 h-4 text-brand" />{t("notifications.preferences")}</h2>
            {prefs && (
              <>
                <label className="flex items-center justify-between text-xs py-1 text-muted"><span>{t("notifications.channel_in_app")}</span><input type="checkbox" checked disabled /></label>
                {toggle("email_enabled", t("notifications.channel_email"))}
                {toggle("sms_enabled", t("notifications.channel_sms"))}
                {toggle("push_enabled", t("notifications.channel_push"))}
                <div className="pt-2 border-t border-line-soft">
                  <p className="text-caption font-semibold flex items-center gap-1.5"><Moon className="w-3.5 h-3.5" />{t("notifications.quiet_hours")}</p>
                  <div className="grid grid-cols-2 gap-2 mt-1">
                    {hourSelect(prefs.quiet_start_hour, (v) => setPrefs({ ...prefs, quiet_start_hour: v }), "pref-quiet-start", t("notifications.from"))}
                    {hourSelect(prefs.quiet_end_hour, (v) => setPrefs({ ...prefs, quiet_end_hour: v }), "pref-quiet-end", t("notifications.to"))}
                  </div>
                  <p className="text-caption text-muted mt-1">{t("notifications.quiet_help")}</p>
                </div>
                <label className="text-caption font-semibold block">{t("notifications.language")}
                  <select value={prefs.language} data-testid="pref-language" onChange={(e) => setPrefs({ ...prefs, language: e.target.value as "en" | "ta" })}
                    className="mt-1 w-full px-2 py-1.5 border border-line rounded-tile text-xs font-normal bg-white">
                    <option value="en">English</option>
                    <option value="ta">தமிழ்</option>
                  </select>
                </label>
                <div className="flex items-center gap-2">
                  <button type="submit" data-testid="prefs-save" className="px-3 py-1.5 bg-brand text-white text-xs font-semibold rounded-tile">{t("notifications.save")}</button>
                  {saved && <span className="text-xs text-success font-semibold" data-testid="prefs-saved">{t("notifications.saved")}</span>}
                </div>
              </>
            )}
          </form>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
