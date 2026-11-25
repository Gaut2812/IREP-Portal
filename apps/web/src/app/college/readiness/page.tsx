"use client";

/** Screen 39 · Placement readiness (college): drill down college → branch → batch → student. The one
 *  readiness score and band (L34), as aggregates and bands (L35): per student only score, band and the
 *  monthly change; never trainer notes or chats. Spec: docs/screens/37-38-39-interviews-drives-readiness.md */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { ChevronRight } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import {
  Badge, Card, CardHeader, DistributionBar, MetricBar, Select, StatTile, Table, THead, Th, Tr, Td, deltaTone,
  type Segment, type Tone,
} from "@/components/ui";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { cn } from "@/lib/cn";

type BandKey = "ready" | "nearly" | "support";
interface Agg { students: number; avg_score: number | null; avg_delta: number | null; bands: Record<BandKey, number> }
interface Group extends Agg { id: string; name: string; level: "branch" | "batch" }
interface StudentRow { id: string; name: string; register_no: string; score: number; band: BandKey; band_label: string; delta: number | null }
interface Data { scope: { branch: { id: string; name: string } | null; batch: { id: string; name: string } | null }; summary: Agg;
  components: { key: string; label: string; avg: number }[]; band_labels: Record<BandKey, string>; groups?: Group[]; students?: StudentRow[] }

const BANDS: BandKey[] = ["ready", "nearly", "support"];
const BAND_TONE: Record<BandKey, Tone> = { ready: "success", nearly: "warning", support: "danger" };

const segments = (a: Agg, labels: Record<BandKey, string>): Segment[] =>
  BANDS.map((k) => ({ key: k, value: a.bands[k], tone: BAND_TONE[k], label: labels[k] }));

const delta = (d: number | null) => d === null ? "–" : `${d > 0 ? "+" : ""}${d}`;
const deltaClass = (d: number | null) => ({ success: "text-success", danger: "text-danger" } as Partial<Record<Tone, string>>)[deltaTone(d)] ?? "text-muted";

/** Component bars: brand blue, amber when the average is the weak spot (< 70). */
const componentTone = (avg: number): Tone => (avg < 70 ? "warning" : avg >= 85 ? "success" : "brand");

export default function ReadinessPage() {
  const { t, language } = useLanguage();
  const [scope, setScope] = useState<{ branch?: string; batch?: string }>({});
  const [band, setBand] = useState<"" | BandKey>("");
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");

  // only the latest request may set state (language or scope can change while one is in flight)
  const latest = useRef(0);
  const load = useCallback(async () => {
    const req = ++latest.current;
    const q = new URLSearchParams({ lang: language });
    if (scope.branch) q.set("branch_id", scope.branch);
    if (scope.batch) q.set("batch_id", scope.batch);
    if (scope.batch && band) q.set("band", band);
    try {
      const res = await fetchApi<Data>(`/college/readiness?${q.toString()}`);
      if (req === latest.current) { setData(res); setError(""); }
    } catch (e) {
      if (req === latest.current) setError(e instanceof ApiError ? String(e.detail) : t("readiness.load_failed"));
    }
  }, [scope, band, language, t]);
  useEffect(() => { load(); }, [load]);

  const s = data?.summary;
  const crumb = "text-brand font-medium hover:underline underline-offset-2";

  return (
    <RoleGuard allowedRoles={["college"]}>
      <AppShell pageTitle={t("readiness.title")} pageSubtitle={t("readiness.help")}>
        <div className="space-y-6 max-w-6xl">
          {error && <p className="text-body text-danger" role="alert">{error}</p>}

          <nav className="flex flex-wrap items-center gap-1.5 text-body" aria-label={t("readiness.path")} data-testid="readiness-path">
            <button type="button" onClick={() => { setScope({}); setBand(""); }} className={crumb}>{t("readiness.college")}</button>
            {data?.scope.branch && <>
              <ChevronRight className="w-4 h-4 text-subtle" aria-hidden />
              <button type="button" onClick={() => { setScope({ branch: data.scope.branch!.id }); setBand(""); }} className={crumb}>{data.scope.branch.name}</button>
            </>}
            {data?.scope.batch && <>
              <ChevronRight className="w-4 h-4 text-subtle" aria-hidden />
              <span className="font-medium text-ink">{data.scope.batch.name}</span>
            </>}
          </nav>

          {s && data && (
            <section className="grid gap-4 sm:grid-cols-3" data-testid="readiness-summary">
              <StatTile label={t("readiness.avg_score")} value={s.avg_score ?? "–"} valueTestId="avg-score"
                hint={`${s.students} ${t("readiness.students")}`} />
              <StatTile label={t("readiness.avg_change")} value={delta(s.avg_delta)} tone={deltaTone(s.avg_delta)}
                hint={t("readiness.this_month")} />
              <StatTile label={t("readiness.bands")}>
                <DistributionBar segments={segments(s, data.band_labels)} legend data-testid="band-bar" />
              </StatTile>
            </section>
          )}

          {data && data.components.length > 0 && (
            <Card data-testid="readiness-components">
              <CardHeader title={t("readiness.components")} />
              <div className="grid gap-3 grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
                {data.components.map((c) => (
                  <MetricBar key={c.key} label={c.label} value={c.avg} tone={componentTone(c.avg)} />
                ))}
              </div>
            </Card>
          )}

          {data?.groups && (
            <Card padded={false} data-testid="readiness-groups">
              <CardHeader className="px-5 pt-5" title={data.scope.branch ? t("readiness.by_batch") : t("readiness.by_branch")}
                subtitle={t("readiness.open_hint")} />
              <Table>
                <THead>
                  <tr>
                    <Th>{data.scope.branch ? t("readiness.batch") : t("readiness.branch")}</Th>
                    <Th align="right">{t("readiness.students_title")}</Th>
                    <Th align="right">{t("readiness.avg_col")}</Th>
                    <Th align="right">{t("readiness.change")}</Th>
                    <Th className="w-[30%] min-w-[180px]">{t("readiness.distribution")}</Th>
                  </tr>
                </THead>
                <tbody>
                  {data.groups.map((g) => {
                    const open = () => { setBand(""); setScope(g.level === "branch" ? { branch: g.id } : { branch: data.scope.branch?.id, batch: g.id }); };
                    const empty = g.students === 0;
                    return (
                      <Tr key={g.id} onClick={empty ? undefined : open}
                        className={cn(empty ? "opacity-50" : "cursor-pointer hover:bg-surface-2 transition-colors")}>
                        <Td>
                          <button type="button" data-testid={`group-${g.id}`} disabled={empty} onClick={(e) => { e.stopPropagation(); open(); }}
                            className="font-medium text-ink text-left hover:text-brand disabled:hover:text-ink">
                            {g.name}
                          </button>
                        </Td>
                        <Td align="right">{g.students}</Td>
                        <Td align="right" className="font-medium">{g.avg_score ?? "–"}</Td>
                        <Td align="right" className={cn("font-medium", deltaClass(g.avg_delta))}>
                          {delta(g.avg_delta)}
                        </Td>
                        <Td><DistributionBar segments={segments(g, data.band_labels)} data-testid="band-bar" /></Td>
                      </Tr>
                    );
                  })}
                </tbody>
              </Table>
            </Card>
          )}

          {data?.students && (
            <Card padded={false} data-testid="readiness-students">
              <CardHeader className="px-5 pt-5" title={t("readiness.students_title")}
                actions={
                  <Select value={band} onChange={(e) => setBand(e.target.value as "" | BandKey)} aria-label={t("readiness.band_filter")} data-testid="band-filter">
                    <option value="">{t("readiness.all_bands")}</option>
                    {BANDS.map((k) => <option key={k} value={k}>{data.band_labels[k]}</option>)}
                  </Select>
                } />
              <Table>
                <THead>
                  <tr>
                    <Th>{t("readiness.student")}</Th>
                    <Th align="right">{t("readiness.score")}</Th>
                    <Th>{t("readiness.band")}</Th>
                    <Th align="right">{t("readiness.change")}</Th>
                  </tr>
                </THead>
                <tbody>
                  {data.students.map((st) => (
                    <Tr key={st.id} data-testid="readiness-student">
                      <Td>
                        <div className="font-medium text-ink">{st.name}</div>
                        <div className="text-caption text-muted">{st.register_no}</div>
                      </Td>
                      <Td align="right" className="font-medium">{st.score}</Td>
                      <Td><Badge tone={BAND_TONE[st.band]}>{st.band_label}</Badge></Td>
                      <Td align="right" className={cn("font-medium", deltaClass(st.delta))}>
                        {delta(st.delta)}
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
              <p className="px-5 py-4 border-t border-line text-label text-muted">{t("readiness.aggregates_note")}</p>
            </Card>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
