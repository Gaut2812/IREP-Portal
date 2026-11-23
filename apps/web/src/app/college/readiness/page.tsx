"use client";

/** Screen 39 · Placement readiness (college): drill down college → branch → batch → student. The one
 *  readiness score and band (L34), as aggregates and bands (L35): per student only score, band and the
 *  monthly change; never trainer notes or chats. Spec: docs/screens/37-38-39-interviews-drives-readiness.md */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";

type BandKey = "ready" | "nearly" | "support";
interface Agg { students: number; avg_score: number | null; avg_delta: number | null; bands: Record<BandKey, number> }
interface Group extends Agg { id: string; name: string; level: "branch" | "batch" }
interface StudentRow { id: string; name: string; register_no: string; score: number; band: BandKey; band_label: string; delta: number | null }
interface Data { scope: { branch: { id: string; name: string } | null; batch: { id: string; name: string } | null }; summary: Agg;
  components: { key: string; label: string; avg: number }[]; band_labels: Record<BandKey, string>; groups?: Group[]; students?: StudentRow[] }

const BAND_STYLE: Record<BandKey, string> = { ready: "bg-[#DCFCE7] text-[#166534]", nearly: "bg-[#FEF3C7] text-[#92400E]", support: "bg-[#FEE2E2] text-[#991B1B]" };
const BAR: Record<BandKey, string> = { ready: "bg-[#22C55E]", nearly: "bg-[#F59E0B]", support: "bg-[#EF4444]" };

function Bands({ a, labels }: { a: Agg; labels: Record<BandKey, string> }) {
  return (
    <div className="space-y-1" data-testid="band-bar">
      <div className="flex h-2 rounded-full overflow-hidden bg-[#F1F5F9]">
        {(["ready", "nearly", "support"] as BandKey[]).map((k) => a.students > 0 && a.bands[k] > 0 && (
          <div key={k} className={BAR[k]} style={{ width: `${(100 * a.bands[k]) / a.students}%` }} title={`${labels[k]}: ${a.bands[k]}`} />
        ))}
      </div>
      <div className="flex flex-wrap gap-2 text-[10px] text-[#475569]">
        {(["ready", "nearly", "support"] as BandKey[]).map((k) => <span key={k}>{labels[k]} {a.bands[k]}</span>)}
      </div>
    </div>
  );
}

const delta = (d: number | null) => d === null ? "–" : `${d > 0 ? "+" : ""}${d}`;

export default function ReadinessPage() {
  const { t, language } = useLanguage();
  const [scope, setScope] = useState<{ branch?: string; batch?: string }>({});
  const [band, setBand] = useState<"" | BandKey>("");
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const q = new URLSearchParams({ lang: language });
    if (scope.branch) q.set("branch_id", scope.branch);
    if (scope.batch) q.set("batch_id", scope.batch);
    if (scope.batch && band) q.set("band", band);
    try { setData(await fetchApi<Data>(`/college/readiness?${q.toString()}`)); setError(""); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : t("readiness.load_failed")); }
  }, [scope, band, language, t]);
  useEffect(() => { load(); }, [load]);

  const s = data?.summary;
  const card = "bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-3";

  return (
    <RoleGuard allowedRoles={["college"]}>
      <AppShell pageTitle={t("readiness.title")}>
        <div className="p-4 md:p-6 space-y-4 max-w-6xl">
          <p className="text-xs text-[#64748B]">{t("readiness.help")}</p>
          {error && <p className="text-xs text-red-600" role="alert">{error}</p>}

          <nav className="flex flex-wrap items-center gap-1 text-xs" aria-label={t("readiness.path")} data-testid="readiness-path">
            <button type="button" onClick={() => { setScope({}); setBand(""); }} className="font-bold text-[#2B5CD0]">{t("readiness.college")}</button>
            {data?.scope.branch && <>›<button type="button" onClick={() => { setScope({ branch: data.scope.branch!.id }); setBand(""); }} className="font-bold text-[#2B5CD0]">{data.scope.branch.name}</button></>}
            {data?.scope.batch && <>›<span className="font-bold text-[#0F1F3A]">{data.scope.batch.name}</span></>}
          </nav>

          {s && data && (
            <section className="grid sm:grid-cols-3 gap-3" data-testid="readiness-summary">
              <div className={card}><div className="text-[11px] text-[#64748B]">{t("readiness.avg_score")}</div>
                <div className="text-2xl font-black text-[#0F1F3A]" data-testid="avg-score">{s.avg_score ?? "–"}</div>
                <div className="text-[11px] text-[#64748B]">{s.students} {t("readiness.students")}</div></div>
              <div className={card}><div className="text-[11px] text-[#64748B]">{t("readiness.avg_change")}</div>
                <div className={`text-2xl font-black ${s.avg_delta !== null && s.avg_delta < 0 ? "text-[#DC2626]" : "text-[#166534]"}`}>{delta(s.avg_delta)}</div>
                <div className="text-[11px] text-[#64748B]">{t("readiness.this_month")}</div></div>
              <div className={card}><div className="text-[11px] text-[#64748B]">{t("readiness.bands")}</div><Bands a={s} labels={data.band_labels} /></div>
            </section>
          )}

          {data && data.components.length > 0 && (
            <section className={card} data-testid="readiness-components">
              <h2 className="text-sm font-black text-[#0F1F3A]">{t("readiness.components")}</h2>
              <ul className="grid sm:grid-cols-2 gap-2">
                {data.components.map((c) => (
                  <li key={c.key} className="text-xs">
                    <div className="flex justify-between"><span>{c.label}</span><b>{c.avg}</b></div>
                    <div className="h-1.5 rounded-full bg-[#F1F5F9]"><div className="h-1.5 rounded-full bg-[#2B5CD0]" style={{ width: `${Math.min(100, c.avg)}%` }} /></div>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {data?.groups && (
            <section className={card} data-testid="readiness-groups">
              <h2 className="text-sm font-black text-[#0F1F3A]">{data.scope.branch ? t("readiness.by_batch") : t("readiness.by_branch")}</h2>
              <ul className="space-y-2">
                {data.groups.map((g) => (
                  <li key={g.id}>
                    <button type="button" data-testid={`group-${g.id}`} disabled={g.students === 0}
                      onClick={() => { setBand(""); setScope(g.level === "branch" ? { branch: g.id } : { branch: data.scope.branch?.id, batch: g.id }); }}
                      className="w-full text-left border border-[#F1F5F9] rounded-lg p-2.5 text-xs grid sm:grid-cols-4 gap-2 items-center hover:bg-[#F8FAFC] disabled:opacity-50">
                      <span className="font-bold text-[#0F1F3A]">{g.name}</span>
                      <span>{g.students} {t("readiness.students")} · {t("readiness.avg")} {g.avg_score ?? "–"}</span>
                      <span>{t("readiness.change")} {delta(g.avg_delta)}</span>
                      <Bands a={g} labels={data.band_labels} />
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {data?.students && (
            <section className={card} data-testid="readiness-students">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-sm font-black text-[#0F1F3A]">{t("readiness.students_title")}</h2>
                <select value={band} onChange={(e) => setBand(e.target.value as "" | BandKey)} aria-label={t("readiness.band_filter")} data-testid="band-filter"
                  className="px-2.5 py-1.5 border border-[#CBD5E1] rounded-lg text-xs">
                  <option value="">{t("readiness.all_bands")}</option>
                  {(["ready", "nearly", "support"] as BandKey[]).map((k) => <option key={k} value={k}>{data.band_labels[k]}</option>)}
                </select>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead><tr className="text-left text-[#64748B] border-b border-[#E2E8F0]">
                    <th className="py-1.5 pr-2">{t("readiness.student")}</th><th className="pr-2">{t("readiness.score")}</th>
                    <th className="pr-2">{t("readiness.band")}</th><th>{t("readiness.change")}</th>
                  </tr></thead>
                  <tbody>
                    {data.students.map((st) => (
                      <tr key={st.id} className="border-b border-[#F1F5F9]" data-testid="readiness-student">
                        <td className="py-1.5 pr-2">{st.name} <span className="text-[#94A3B8]">{st.register_no}</span></td>
                        <td className="pr-2 font-bold">{st.score}</td>
                        <td className="pr-2"><span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${BAND_STYLE[st.band]}`}>{st.band_label}</span></td>
                        <td className={st.delta !== null && st.delta < 0 ? "text-[#DC2626]" : "text-[#166534]"}>{delta(st.delta)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-[11px] text-[#64748B]">{t("readiness.aggregates_note")}</p>
            </section>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
