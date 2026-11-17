"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi } from "@/lib/api";
import { Heart, MessageSquare, AlertCircle, RefreshCw, CheckCircle2, WifiOff, ExternalLink, Calendar, Award, Users } from "lucide-react";

interface Overview {
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
      try { localStorage.setItem(CACHE_KEY, JSON.stringify({ at: new Date().toISOString(), lang: language, id, data: res })); } catch { /* ignore */ }
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
  const card = "bg-white p-4 rounded-2xl border border-[#E2E8F0] shadow-sm";

  return (
    <RoleGuard allowedRoles={["parent"]}>
      <AppShell pageTitle={data ? `${t("parent_view.title")} · ${data.ward.name} (${data.ward.details})` : t("parent_view.title")}>
        {/* One thumb-reach column, 360px first; widens on desktop */}
        <div className="w-full max-w-[420px] md:max-w-3xl mx-auto space-y-4" data-testid="parent-view">

          {(offline || cachedAt) && (
            <div className="flex items-center gap-2 bg-[#FEF3C7] border border-[#FDE68A] text-[#92400E] text-xs rounded-xl p-3" data-testid="offline-banner">
              <WifiOff className="w-4 h-4 flex-shrink-0" />
              <span>{fill(t(offline ? "parent_view.offline_banner" : "parent_view.cached_banner"), { d: (cachedAt || "").slice(0, 10) })}</span>
            </div>
          )}

          {/* Header strip: ward + language toggle (always visible) */}
          <div className="bg-[#14284B] text-white rounded-2xl p-4 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="text-[10px] uppercase tracking-wider text-[#94A3B8]">{t("parent_view.your_ward")}</div>
              {children.length > 1 ? (
                <select value={childId} onChange={(e) => setChildId(e.target.value)} className="mt-0.5 bg-white/10 text-white text-sm font-bold rounded-lg px-2 py-1 focus:outline-none" aria-label={t("parent_view.select_child")} data-testid="child-select">
                  {children.map((c) => <option key={c.id} value={c.id} className="text-[#0F1F3A]">{c.name} · Sem {c.semester} · {c.branch}</option>)}
                </select>
              ) : (
                <div className="text-sm font-bold truncate" data-testid="ward-name">{data ? `${data.ward.name} · Sem ${data.ward.semester} · ${data.ward.branch}` : "…"}</div>
              )}
            </div>
            <button onClick={toggleLanguage} className="text-[11px] font-bold px-2.5 py-1 rounded-lg bg-white/15 hover:bg-white/25 flex-shrink-0" aria-label="Toggle Tamil / English">
              {language === "en" ? "தமிழ்" : "EN"}
            </button>
          </div>

          {loading && (
            <div className="space-y-4 animate-pulse" aria-busy="true" aria-label={t("parent_view.loading")}>
              <div className="h-24 bg-white rounded-2xl border border-[#E2E8F0]" />
              <div className="grid grid-cols-2 gap-3"><div className="h-20 bg-white rounded-2xl border border-[#E2E8F0]" /><div className="h-20 bg-white rounded-2xl border border-[#E2E8F0]" /></div>
              <div className="h-48 bg-white rounded-2xl border border-[#E2E8F0]" />
            </div>
          )}

          {!loading && error && (
            <div className="bg-white rounded-2xl border border-[#FECACA] p-6 text-center space-y-3">
              <AlertCircle className="w-8 h-8 text-[#D93636] mx-auto" />
              <h2 className="text-base font-bold text-[#0F1F3A]">{t("parent_view.error_title")}</h2>
              <p className="text-xs text-[#64748B]">{error}</p>
              <button onClick={load} className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg"><RefreshCw className="w-3.5 h-3.5" /> {t("parent_view.retry")}</button>
            </div>
          )}

          {!loading && !error && !data && (
            <div className="bg-white rounded-2xl border border-[#E2E8F0] p-6 text-center text-xs text-[#64748B]">{t("parent_view.no_child")}</div>
          )}

          {!loading && !error && data && k && (
            <>
              {/* Readiness card */}
              <div className="bg-[#EFF6FF] border border-[#BFDBFE] p-4 rounded-2xl" data-testid="readiness-card">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-[#1D4ED8] font-semibold">{t("parent_view.readiness_score")}</span>
                  <span className={BAND_CHIP[k.readiness_band] || "chip-blue"}>{k.readiness_band_label}</span>
                </div>
                <div className="text-4xl font-black text-[#1E3A8A] mt-1">
                  {k.readiness_score}
                  <span className={`text-sm ml-2 ${k.readiness_delta >= 0 ? "text-[#15803D]" : "text-[#D93636]"}`}>{k.readiness_delta >= 0 ? "▲" : "▼"} {Math.abs(k.readiness_delta)}</span>
                </div>
              </div>

              {/* Attendance / problems / certs */}
              <div className="grid grid-cols-2 gap-3" data-testid="parent-kpis">
                <div className={card}>
                  <div className="text-[10px] text-[#64748B] uppercase tracking-wide">{t("parent_view.attendance")}</div>
                  <div className="flex items-baseline gap-2"><span className="text-2xl font-black text-[#0F1F3A]">{k.attendance_pct}%</span><span className={k.attendance_good ? "chip-green" : "chip-amber"}>{k.attendance_note}</span></div>
                  <div className="text-[10px] text-[#64748B]">{fill(t("parent_view.sessions"), { a: k.sessions_attended, b: k.sessions_total })}</div>
                </div>
                <div className={card}>
                  <div className="text-[10px] text-[#64748B] uppercase tracking-wide">{t("parent_view.problems_solved")}</div>
                  <div className="text-2xl font-black text-[#0F1F3A]">{k.problems_solved}</div>
                </div>
                <div className={`${card} col-span-2 flex items-center justify-between`}>
                  <div>
                    <div className="text-[10px] text-[#64748B] uppercase tracking-wide">{t("parent_view.certifications")}</div>
                    <div className="text-2xl font-black text-[#0F1F3A]">{k.certifications}</div>
                  </div>
                  <div className="text-xs text-[#2B5CD0] font-semibold flex items-center gap-1"><Award className="w-4 h-4" />{k.cert_note}</div>
                </div>
              </div>

              {/* Monthly progress card */}
              <div className={`${card} space-y-3`} data-testid="monthly-card">
                <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
                  <h3 className="font-bold text-xs text-[#0F1F3A]">{t("parent_view.monthly_card")}</h3>
                  {data.monthly_card && <span className="text-[11px] font-semibold text-[#64748B]">{data.monthly_card.month}</span>}
                </div>
                {!data.monthly_card ? (
                  <p className="text-xs text-[#64748B] py-4 text-center">{t("parent_view.no_card")}</p>
                ) : (
                  <>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs text-left">
                        <thead><tr className="border-b border-[#E2E8F0] text-[#64748B] text-[11px]">
                          <th className="pb-2 font-semibold">{t("parent_view.area")}</th><th className="pb-2 font-semibold">{data.monthly_card.prev_month}</th>
                          <th className="pb-2 font-semibold">{data.monthly_card.month}</th><th className="pb-2 font-semibold text-right">{t("parent_view.status")}</th>
                        </tr></thead>
                        <tbody className="divide-y divide-[#E2E8F0]">
                          {data.monthly_card.rows.map((r) => (
                            <tr key={r.area}>
                              <td className="py-2.5 font-bold text-[#0F1F3A]">{r.area}</td>
                              <td className="py-2.5 text-[#64748B]">{r.prev}</td>
                              <td className="py-2.5 font-semibold text-[#0F1F3A]">{r.curr}</td>
                              <td className="py-2.5 text-right"><span className={CHIP[r.color] || "chip-blue"}>{r.status}</span></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {data.monthly_card.how_to_help && (
                      <div className="bg-[#EFF6FF] border border-[#BFDBFE] rounded-xl p-3 flex items-start gap-2">
                        <Heart className="w-4 h-4 text-[#2B5CD0] flex-shrink-0 mt-0.5" />
                        <div>
                          <div className="text-xs font-bold text-[#1D4ED8]">{t("parent_view.how_you_can_help")}</div>
                          <p className="text-xs text-[#1E3A8A] mt-0.5 leading-relaxed">{data.monthly_card.how_to_help}</p>
                        </div>
                      </div>
                    )}
                    {data.monthly_card.trainer_remark && (
                      <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-3">
                        <div className="text-[10px] font-bold text-[#2B5CD0] uppercase tracking-wider">{t("parent_view.trainer_remark")} · {data.monthly_card.month}</div>
                        <p className="text-xs text-[#334155] italic mt-1 leading-relaxed">“{data.monthly_card.trainer_remark}”</p>
                        <div className="text-[10px] text-right font-bold text-[#64748B] mt-1">– {data.monthly_card.trainer_name}</div>
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* Portfolio */}
              <div className={`${card} space-y-2`}>
                <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
                  <h3 className="font-bold text-xs text-[#0F1F3A]">{t("parent_view.portfolio")}</h3>
                  <Link href="/parent/portfolio" className="text-[11px] font-semibold text-[#2B5CD0] flex items-center gap-1">{t("parent_view.open_portfolio")} <ExternalLink className="w-3 h-3" /></Link>
                </div>
                <div className="text-xs space-y-1.5">
                  <div className="flex justify-between"><span className="text-[#64748B]">{t("parent_view.github")}</span><span className="font-bold text-[#0F1F3A]">{fill(t("parent_view.projects"), { n: data.portfolio.github_projects })}</span></div>
                  {data.portfolio.live_project && <div className="flex justify-between"><span className="text-[#64748B]">{t("parent_view.live")}</span><a href={data.portfolio.live_url || "#"} className="font-bold text-[#2B5CD0] truncate ml-2" target="_blank" rel="noreferrer">{data.portfolio.live_project}</a></div>}
                  {data.portfolio.demo_video && <div className="flex justify-between"><span className="text-[#64748B]">{t("parent_view.demo_video")}</span><span className="font-semibold text-[#0F1F3A]">{data.portfolio.demo_video}</span></div>}
                </div>
              </div>

              {/* Upcoming + RSVP */}
              <div className={`${card} space-y-3`} data-testid="upcoming">
                <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
                  <h3 className="font-bold text-xs text-[#0F1F3A]">{t("parent_view.upcoming")}</h3><Calendar className="w-3.5 h-3.5 text-[#64748B]" />
                </div>
                {data.upcoming.length === 0 ? (
                  <p className="text-xs text-[#64748B] py-3 text-center">{t("parent_view.no_upcoming")}</p>
                ) : data.upcoming.map((e) => (
                  <div key={e.id} className={`rounded-xl p-3 ${e.rsvp_enabled ? "bg-gradient-to-br from-[#F0FDF4] to-[#DCFCE7] border border-[#BBF7D0]" : "bg-[#F8FAFC] border border-[#E2E8F0]"}`} data-testid={`event-${e.id}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-xs font-bold text-[#0F1F3A]">{e.title}</div>
                        <div className="text-[11px] text-[#64748B]">{e.when}{e.rsvp_enabled ? ` · ${t("parent_view.invited")}` : ""}</div>
                      </div>
                      {e.rsvp_status && <span className={e.rsvp_status === "yes" ? "chip-green" : e.rsvp_status === "no" ? "chip-red" : "chip-amber"}>{t(`parent_view.rsvp_${e.rsvp_status}`)}</span>}
                    </div>
                    {e.rsvp_enabled && (
                      <div className="flex gap-2 pt-2">
                        <button type="button" disabled={rsvpBusy === e.id} onClick={() => rsvp(e.id, "yes")} className="flex-1 py-2 bg-[#2BB3A0] hover:bg-[#249B8A] text-white font-bold text-xs rounded-lg shadow-sm disabled:opacity-50" data-testid="rsvp-yes">
                          {e.rsvp_status === "yes" ? `${t("parent_view.rsvp_yes")} ✓` : t("parent_view.rsvp")}
                        </button>
                        <button type="button" disabled={rsvpBusy === e.id} onClick={() => rsvp(e.id, "maybe")} className="px-3 py-2 border border-[#CBD5E1] text-[#0F1F3A] font-bold text-xs rounded-lg bg-white disabled:opacity-50">{t("parent_view.rsvp_maybe")}</button>
                        <button type="button" disabled={rsvpBusy === e.id} onClick={() => rsvp(e.id, "no")} className="px-3 py-2 border border-[#CBD5E1] text-[#0F1F3A] font-bold text-xs rounded-lg bg-white disabled:opacity-50">{t("parent_view.rsvp_no")}</button>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Message trainer */}
              <Link href="/parent/messages" className="block bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-sm hover:border-[#2B5CD0]" data-testid="message-trainer">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-9 h-9 rounded-full bg-[#2B5CD0] text-white flex items-center justify-center"><MessageSquare className="w-4 h-4" /></div>
                    <div>
                      <div className="text-xs font-bold text-[#0F1F3A]">{t("parent_view.message_trainer")}</div>
                      <div className="text-[11px] text-[#64748B] flex items-center gap-1"><Users className="w-3 h-3" />{data.trainers.map((tr) => tr.name).join(", ") || "—"}</div>
                    </div>
                  </div>
                  <span className="text-[10px] text-[#64748B]">{fill(t("parent_view.replies_within"), { h: data.reply_promise_hours })}</span>
                </div>
              </Link>
            </>
          )}
        </div>
        {toast && (
          <div role="status" className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-[#0F1F3A] text-white text-xs font-semibold px-4 py-3 rounded-xl shadow-2xl flex items-center gap-2" data-testid="toast">
            <CheckCircle2 className="w-4 h-4 text-[#2BB3A0]" /> {toast}
          </div>
        )}
      </AppShell>
    </RoleGuard>
  );
}
