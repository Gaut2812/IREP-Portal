"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { Button, buttonClass } from "@/components/ui";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi } from "@/lib/api";
import { Heart, MessageSquare, AlertCircle, RefreshCw, CheckCircle2, WifiOff, ExternalLink, Calendar, Award, Users } from "lucide-react";

interface Overview {
  /** Screen 48: without parent-data consent the API returns only ward id/name and the consent text */
  consent_required?: boolean;
  consent_state?: "missing" | "withdrawn";
  consent?: { purpose: string; title: string; body: string };
  ward: { id: string; name: string; semester: number; branch: string; track: string; details: string; batch: string; college: string };
  kpis: {
    readiness_score: number; readiness_delta: number; readiness_band: string; readiness_band_label: string;
    attendance_pct: number; attendance_note: string; attendance_good: boolean; sessions_attended: number; sessions_total: number;
    problems_solved: number; certifications: number; cert_note: string;
  };
  monthly_card: {
    id: string; month: string; prev_month: string; rows: { area: string; prev: string; curr: string; status: string; color: string }[];
    how_to_help: string | null; trainer_remark: string | null; trainer_name: string | null; status: string; released_at: string | null;
  } | null;
  portfolio: { github_projects: number; live_project: string | null; live_url: string | null; demo_video: string | null };
  upcoming: { id: string; title: string; kind: string; when: string; date: string; location: string | null; description: string | null; rsvp_enabled: boolean; rsvp_status: string | null; guests: number }[];
  trainers: { trainer_id: string; user_id: string; name: string; designation: string }[];
  reply_promise_hours: number;
  /** L31: open flags the trainer raised with the parent */
  support_alerts?: { id: string; issue: string; next_step: string; since: string }[];
  /** L30: announcements from the college and trainers */
  announcements?: { id: string; title: string; body: string; from: string; at: string | null }[];
}
interface Child { id: string; name: string; semester: number; branch: string; batch_name: string }

const CACHE_KEY = "irep_parent_overview_cache";
const CHIP: Record<string, string> = { green: "chip-green", amber: "chip-amber", red: "chip-red", blue: "chip-blue" };
const BAND_CHIP: Record<string, string> = { "Placement Ready": "chip-green", "Nearly Ready": "chip-amber", "Needs Support": "chip-red" };

function fill(template: string, vars: Record<string, string | number>) {
  return Object.entries(vars).reduce((acc, [k, v]) => acc.replace(`{${k}}`, String(v)), template);
}

export default function ParentViewPage() {
  const { t, language, toggleLanguage } = useLanguage();
  const [children, setChildren] = useState<Child[]>([]);
  const [childId, setChildId] = useState<string>("");
  const [data, setData] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cachedAt, setCachedAt] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [rsvpBusy, setRsvpBusy] = useState<string | null>(null);

  // Install the service worker for the installable, offline-capable parent app
  useEffect(() => {
    if (typeof navigator !== "undefined" && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => undefined);
    }
    const on = () => setOffline(false);
    const off = () => setOffline(true);
    setOffline(typeof navigator !== "undefined" && navigator.onLine === false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);

  const [consentBusy, setConsentBusy] = useState(false);
  const grantConsent = async () => {
    if (!data?.consent) return;
    setConsentBusy(true);
    try {
      await fetchApi("/consent", { method: "POST", body: JSON.stringify({ purpose: data.consent.purpose, status: "granted", student_id: data.ward.id }) });
      await load();
    } catch (err: any) {
      setError(err?.detail || err?.message || "error");
    } finally {
      setConsentBusy(false);
    }
  };

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const kids = await fetchApi<{ children: Child[] }>("/parent/me/children");
      setChildren(kids.children);
      const id = childId || kids.children[0]?.id || "";
      if (!id) { setData(null); setLoading(false); return; }
      if (!childId) setChildId(id);
      const res = await fetchApi<Overview>(`/parent/children/${id}/overview?lang=${language}`);
      setData(res);
      setCachedAt(null);
      try {
        // never keep an offline copy of a child's data without consent
        if (res.consent_required) localStorage.removeItem(CACHE_KEY);
        else localStorage.setItem(CACHE_KEY, JSON.stringify({ at: new Date().toISOString(), lang: language, id, data: res }));
      } catch { /* ignore */ }
    } catch (err: any) {
      // Offline or API down: show the last cached summary if there is one
      try {
        const raw = localStorage.getItem(CACHE_KEY);
        if (raw) {
          const cached = JSON.parse(raw);
          setData(cached.data);
          setCachedAt(cached.at);
          setError(null);
          setLoading(false);
          return;
        }
      } catch { /* ignore */ }
      setError(err?.detail || err?.message || "error");
    } finally {
      setLoading(false);
    }
  }, [childId, language]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(id);
  }, [toast]);

  const rsvp = async (eventId: string, status: "yes" | "no" | "maybe") => {
    setRsvpBusy(eventId);
    try {
      const res = await fetchApi<{ rsvp_status: string; guests: number }>(`/parent/events/${eventId}/rsvp`, {
        method: "POST", body: JSON.stringify({ status, guests: status === "yes" ? 1 : 0, child_id: childId || undefined }),
      });
      setData((prev) => prev ? { ...prev, upcoming: prev.upcoming.map((e) => e.id === eventId ? { ...e, rsvp_status: res.rsvp_status, guests: res.guests } : e) } : prev);
      setToast(t("parent_view.rsvp_saved"));
    } catch {
      setToast(t("parent_view.rsvp_failed"));
    } finally {
      setRsvpBusy(null);
    }
  };

  const k = data?.kpis;
  const card = "bg-surface p-5 rounded-card border border-line shadow-card";

  return (
    <RoleGuard allowedRoles={["parent"]}>
      <AppShell pageTitle={data ? `${t("parent_view.title")} · ${data.ward.name} (${data.ward.details})` : t("parent_view.title")}>
        {/* One thumb-reach column, 360px first; widens on desktop */}
        <div className="w-full max-w-[420px] md:max-w-3xl space-y-4 md:space-y-6" data-testid="parent-view">

          {(offline || cachedAt) && (
            <div className="flex items-center gap-2 bg-warning-soft border border-warning-line text-warning text-xs rounded-card p-3" data-testid="offline-banner">
              <WifiOff className="w-4 h-4 flex-shrink-0" />
              <span>{fill(t(offline ? "parent_view.offline_banner" : "parent_view.cached_banner"), { d: (cachedAt || "").slice(0, 10) })}</span>
            </div>
          )}

          {/* Header strip: ward + language toggle (always visible) */}
          <div className="bg-navy text-white rounded-card p-5 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="text-label text-white/70">{t("parent_view.your_ward")}</div>
              {children.length > 1 ? (
                <select value={childId} onChange={(e) => setChildId(e.target.value)} className="mt-0.5 bg-white/10 text-white text-body font-semibold rounded-tile px-2 py-1 focus:outline-none" aria-label={t("parent_view.select_child")} data-testid="child-select">
                  {children.map((c) => <option key={c.id} value={c.id} className="text-ink">{c.name} · Sem {c.semester} · {c.branch}</option>)}
                </select>
              ) : (
                <div className="text-heading font-semibold truncate" data-testid="ward-name">{data ? `${data.ward.name} · Sem ${data.ward.semester} · ${data.ward.branch}` : "…"}</div>
              )}
            </div>
            <button onClick={toggleLanguage} className="text-label font-medium h-8 px-3 rounded-tile bg-white/15 hover:bg-white/25 flex-shrink-0" aria-label="Toggle Tamil / English">
              {language === "en" ? "தமிழ்" : "EN"}
            </button>
          </div>

          {loading && (
            <div className="space-y-4 animate-pulse" aria-busy="true" aria-label={t("parent_view.loading")}>
              <div className="h-24 bg-white rounded-card border border-line" />
              <div className="grid grid-cols-2 gap-3"><div className="h-20 bg-white rounded-card border border-line" /><div className="h-20 bg-white rounded-card border border-line" /></div>
              <div className="h-48 bg-white rounded-card border border-line" />
            </div>
          )}

          {!loading && error && (
            <div className="bg-white rounded-card border border-danger-line p-6 text-center space-y-3">
              <AlertCircle className="w-8 h-8 text-danger mx-auto" />
              <h2 className="text-heading font-semibold text-ink">{t("parent_view.error_title")}</h2>
              <p className="text-body text-muted">{error}</p>
              <Button onClick={load}><RefreshCw className="w-4 h-4" /> {t("parent_view.retry")}</Button>
            </div>
          )}

          {!loading && !error && !data && (
            <div className="bg-white rounded-card border border-line p-6 text-center text-body text-muted">{t("parent_view.no_child")}</div>
          )}

          {!loading && !error && data?.consent_required && data.consent && (
            <div className="bg-white rounded-card border border-brand-line p-5 space-y-3" data-testid="consent-card">
              <h2 className="text-heading font-semibold text-ink">{data.consent.title}</h2>
              <p className="text-body text-ink-soft leading-relaxed">{data.consent.body}</p>
              <p className="text-caption text-muted">{data.ward.name}</p>
              <button type="button" disabled={consentBusy} onClick={grantConsent} data-testid="consent-agree"
                className={buttonClass("primary", "md", "w-full")}>
                {t("parent_view.consent_agree")}
              </button>
            </div>
          )}

          {!loading && !error && data && !data.consent_required && k && (
            <>
              {(data.support_alerts || []).map((al) => (
                <Link key={al.id} href="/parent/messages" className="block bg-warning-faint border border-warning-line rounded-card p-4" data-testid="support-alert">
                  <div className="text-label font-semibold text-warning">{t("parent_view.support_alert")}</div>
                  <div className="text-body text-warning mt-1">{al.issue} · {t("parent_view.next_step")}: {al.next_step}</div>
                  <div className="text-label text-warning mt-1 font-medium">{t("parent_view.support_reply")}</div>
                </Link>
              ))}
              {(data.announcements || []).length > 0 && (
                <div className="bg-surface border border-line rounded-card shadow-card p-5 space-y-3" data-testid="announcements">
                  <div className="text-heading font-semibold text-ink">{t("parent_view.announcements")}</div>
                  {(data.announcements || []).map((an) => (
                    <div key={an.id} className="text-body border-t border-line-soft pt-3 first:border-0 first:pt-0" data-testid="announcement">
                      <div className="font-medium text-ink">{an.title}</div>
                      <div className="text-ink-soft">{an.body}</div>
                      <div className="text-caption text-subtle">{an.from === "college" ? t("parent_view.from_college") : t("parent_view.from_trainer")}{an.at ? ` · ${an.at}` : ""}</div>
                    </div>
                  ))}
                </div>
              )}
              {/* Readiness card */}
              <div className="bg-surface border border-line shadow-card p-5 rounded-card" data-testid="readiness-card">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-label font-medium text-muted">{t("parent_view.readiness_score")}</span>
                  <span className={BAND_CHIP[k.readiness_band] || "chip-blue"}>{k.readiness_band_label}</span>
                </div>
                <div className="text-kpi font-semibold text-ink tabular mt-2">
                  {k.readiness_score}
                  <span className={`text-label font-medium ml-2 ${k.readiness_delta >= 0 ? "text-success" : "text-danger"}`}>{k.readiness_delta >= 0 ? "▲" : "▼"} {Math.abs(k.readiness_delta)}</span>
                </div>
              </div>

              {/* Attendance / problems / certs */}
              <div className="grid grid-cols-2 gap-3 md:gap-4" data-testid="parent-kpis">
                <div className={card}>
                  <div className="text-label font-medium text-muted">{t("parent_view.attendance")}</div>
                  <div className="mt-2 flex flex-wrap items-baseline gap-2"><span className="text-kpi font-semibold text-ink tabular">{k.attendance_pct}%</span><span className={k.attendance_good ? "chip-green" : "chip-amber"}>{k.attendance_note}</span></div>
                  <div className="mt-1.5 text-label text-muted">{fill(t("parent_view.sessions"), { a: k.sessions_attended, b: k.sessions_total })}</div>
                </div>
                <div className={card}>
                  <div className="text-label font-medium text-muted">{t("parent_view.problems_solved")}</div>
                  <div className="mt-2 text-kpi font-semibold text-ink tabular">{k.problems_solved}</div>
                </div>
                <div className={`${card} col-span-2 flex items-center justify-between`}>
                  <div>
                    <div className="text-label font-medium text-muted">{t("parent_view.certifications")}</div>
                    <div className="mt-2 text-kpi font-semibold text-ink tabular">{k.certifications}</div>
                  </div>
                  <div className="text-label text-brand font-medium flex items-center gap-1"><Award className="w-4 h-4" />{k.cert_note}</div>
                </div>
              </div>

              {/* Monthly progress card */}
              <div className={`${card} space-y-4`} data-testid="monthly-card">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-heading font-semibold text-ink">{t("parent_view.monthly_card")}</h3>
                  {data.monthly_card && <span className="text-label text-muted">{data.monthly_card.month}</span>}
                </div>
                {!data.monthly_card ? (
                  <p className="text-body text-muted py-4 text-center">{t("parent_view.no_card")}</p>
                ) : (
                  <>
                    <div className="overflow-x-auto">
                      <table className="w-full text-body text-left">
                        <thead><tr className="border-b border-line text-muted text-caption">
                          <th className="pb-2 font-medium">{t("parent_view.area")}</th><th className="pb-2 px-1 font-medium"><span className="sm:hidden">{data.monthly_card.prev_month.slice(0, 3)}</span><span className="hidden sm:inline">{data.monthly_card.prev_month}</span></th>
                          <th className="pb-2 px-1 font-medium"><span className="sm:hidden">{data.monthly_card.month.slice(0, 3)}</span><span className="hidden sm:inline">{data.monthly_card.month}</span></th><th className="pb-2 font-medium text-right">{t("parent_view.status")}</th>
                        </tr></thead>
                        <tbody className="divide-y divide-line-soft">
                          {data.monthly_card.rows.map((r) => (
                            <tr key={r.area}>
                              <td className="py-3 text-ink">{r.area}</td>
                              <td className="py-3 px-1 text-muted">{r.prev}</td>
                              <td className="py-3 px-1 font-medium text-ink">{r.curr}</td>
                              <td className="py-3 text-right"><span className={CHIP[r.color] || "chip-blue"}>{r.status}</span></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {data.monthly_card.how_to_help && (
                      <div className="bg-brand-soft border border-brand-line rounded-card p-3 flex items-start gap-2">
                        <Heart className="w-4 h-4 text-brand flex-shrink-0 mt-0.5" />
                        <div>
                          <div className="text-label font-semibold text-info">{t("parent_view.how_you_can_help")}</div>
                          <p className="text-body text-info mt-0.5 leading-relaxed">{data.monthly_card.how_to_help}</p>
                        </div>
                      </div>
                    )}
                    {data.monthly_card.trainer_remark && (
                      <div className="bg-surface-2 border border-line rounded-card p-3">
                        <div className="text-label font-medium text-brand">{t("parent_view.trainer_remark")} · {data.monthly_card.month}</div>
                        <p className="text-body text-ink-soft italic mt-1 leading-relaxed">“{data.monthly_card.trainer_remark}”</p>
                        <div className="text-label text-right text-muted mt-1">– {data.monthly_card.trainer_name}</div>
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* Portfolio */}
              <div className={`${card} space-y-4`}>
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-heading font-semibold text-ink">{t("parent_view.portfolio")}</h3>
                  <Link href="/parent/portfolio" className="text-label font-medium text-brand hover:underline underline-offset-2 flex items-center gap-1">{t("parent_view.open_portfolio")} <ExternalLink className="w-4 h-4" /></Link>
                </div>
                <div className="text-body space-y-2">
                  <div className="flex justify-between"><span className="text-muted">{t("parent_view.github")}</span><span className="font-semibold text-ink">{fill(t("parent_view.projects"), { n: data.portfolio.github_projects })}</span></div>
                  {data.portfolio.live_project && <div className="flex justify-between"><span className="text-muted">{t("parent_view.live")}</span><a href={data.portfolio.live_url || "#"} className="font-semibold text-brand truncate ml-2" target="_blank" rel="noreferrer">{data.portfolio.live_project}</a></div>}
                  {data.portfolio.demo_video && <div className="flex justify-between"><span className="text-muted">{t("parent_view.demo_video")}</span><span className="font-semibold text-ink">{data.portfolio.demo_video}</span></div>}
                </div>
              </div>

              {/* Upcoming + RSVP */}
              <div className={`${card} space-y-3`} data-testid="upcoming">
                <div className="flex items-center justify-between gap-2 mb-1">
                  <h3 className="text-heading font-semibold text-ink">{t("parent_view.upcoming")}</h3><Calendar className="w-4 h-4 text-subtle" />
                </div>
                {data.upcoming.length === 0 ? (
                  <p className="text-body text-muted py-3 text-center">{t("parent_view.no_upcoming")}</p>
                ) : data.upcoming.map((e) => (
                  <div key={e.id} className={`rounded-tile p-4 ${e.rsvp_enabled ? "bg-success-faint border border-success-line" : "bg-surface-2 border border-line"}`} data-testid={`event-${e.id}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-body font-medium text-ink">{e.title}</div>
                        <div className="text-label text-muted">{e.when}{e.rsvp_enabled ? ` · ${t("parent_view.invited")}` : ""}</div>
                      </div>
                      {e.rsvp_status && <span className={e.rsvp_status === "yes" ? "chip-green" : e.rsvp_status === "no" ? "chip-red" : "chip-amber"}>{t(`parent_view.rsvp_${e.rsvp_status}`)}</span>}
                    </div>
                    {e.rsvp_enabled && (
                      <div className="flex gap-2 pt-3">
                        <button type="button" disabled={rsvpBusy === e.id} onClick={() => rsvp(e.id, "yes")} className={buttonClass("primary", "md", "flex-1")} data-testid="rsvp-yes">
                          {e.rsvp_status === "yes" ? `${t("parent_view.rsvp_yes")} ✓` : t("parent_view.rsvp")}
                        </button>
                        <button type="button" disabled={rsvpBusy === e.id} onClick={() => rsvp(e.id, "maybe")} className={buttonClass("secondary")}>{t("parent_view.rsvp_maybe")}</button>
                        <button type="button" disabled={rsvpBusy === e.id} onClick={() => rsvp(e.id, "no")} className={buttonClass("secondary")}>{t("parent_view.rsvp_no")}</button>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Message trainer */}
              <Link href="/parent/messages" className="block bg-surface border border-line rounded-card p-5 shadow-card hover:border-brand transition-colors" data-testid="message-trainer">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 rounded-full bg-brand text-white flex items-center justify-center flex-shrink-0"><MessageSquare className="w-4 h-4" /></div>
                    <div className="min-w-0">
                      <div className="text-body font-semibold text-ink">{t("parent_view.message_trainer")}</div>
                      <div className="text-label text-muted flex items-center gap-1"><Users className="w-4 h-4" />{data.trainers.map((tr) => tr.name).join(", ") || "—"}</div>
                    </div>
                  </div>
                  <span className="text-label text-muted text-right">{fill(t("parent_view.replies_within"), { h: data.reply_promise_hours })}</span>
                </div>
              </Link>
            </>
          )}
        </div>
        {toast && (
          <div role="status" className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-ink text-white text-body font-medium px-4 py-3 rounded-card shadow-pop flex items-center gap-2" data-testid="toast">
            <CheckCircle2 className="w-4 h-4 text-teal" /> {toast}
          </div>
        )}
      </AppShell>
    </RoleGuard>
  );
}
