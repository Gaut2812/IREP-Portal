"use client";

/** Screen 04 · Trainer batches: my batches and roster. Spec: docs/screens/04-trainer-batches.md */
import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { AlertTriangle, Users } from "lucide-react";

interface BatchRow {
  id: string; short_name: string; name: string; semester: number; academic_year: string; role: string; students: number;
  avg_readiness: number | null; avg_attendance: number | null; branch: string | null; branch_code: string | null; college: string | null;
}
interface RosterRow { id: string; name: string; register_no: string; readiness_score: number; readiness_band: string; attendance_pct: number; open_flags: number; pending_roster_request: boolean }

const BAND: Record<string, string> = { "Placement Ready": "bg-success-soft text-success", "Nearly Ready": "bg-warning-soft text-warning", "Needs Support": "bg-danger-soft text-danger" };

export default function TrainerBatchesPage() {
  const { t } = useLanguage();
  const [batches, setBatches] = useState<BatchRow[] | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [roster, setRoster] = useState<RosterRow[] | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetchApi<{ batches: BatchRow[] }>("/trainer/batches")
      .then((r) => { setBatches(r.batches); if (r.batches[0]) setSelected((s) => s || r.batches[0].id); })
      .catch((e) => setError(e instanceof ApiError ? e.detail : t("trainer_batches.load_failed")));
  }, [t]);

  const loadRoster = useCallback(async () => {
    if (!selected) return;
    try {
      setRoster((await fetchApi<{ students: RosterRow[] }>(`/trainer/batches/${selected}/roster`)).students);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("trainer_batches.load_failed"));
    }
  }, [selected, t]);

  useEffect(() => { loadRoster(); }, [loadRoster]);

  const shown = roster?.filter((s) => !filter.trim() || s.name.toLowerCase().includes(filter.toLowerCase()) || s.register_no.includes(filter.trim()));

  return (
    <RoleGuard allowedRoles={["trainer"]}>
      <AppShell pageTitle={t("trainer_batches.title")}>
        <div className="space-y-6 max-w-6xl">
          {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
          {batches && batches.length === 0 && (
            <div className="bg-white rounded-card border border-dashed border-line-strong p-6 text-center text-xs text-muted" data-testid="no-batches">{t("trainer_batches.no_batches")}</div>
          )}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2" data-testid="batch-cards">
            {batches?.map((b) => (
              <button key={b.id} type="button" onClick={() => setSelected(b.id)} data-testid={`batch-card-${b.short_name}`} aria-pressed={selected === b.id}
                className={`text-left bg-white rounded-card border p-3 ${selected === b.id ? "border-brand ring-1 ring-brand" : "border-line"}`}>
                <div className="text-sm font-semibold text-ink">{b.short_name}</div>
                <div className="text-caption text-ink-soft truncate" data-testid="batch-branch">{[b.branch, b.college].filter(Boolean).join(" · ")}</div>
                <div className="text-caption text-muted">{t("trainer_batches.sem")} {b.semester} · {b.academic_year} · {b.students} {t("trainer_batches.students")}</div>
                <div className="text-caption text-muted">{t("trainer_batches.readiness")} {b.avg_readiness ?? "—"} · {t("trainer_batches.attendance")} {b.avg_attendance ?? "—"}%</div>
                {b.role === "substitute" && <span className="text-caption text-warning font-semibold">{t("trainer_batches.substitute")}</span>}
              </button>
            ))}
          </div>
          {roster && (
            <section className="bg-white rounded-card border border-line p-4 space-y-2">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <h2 className="text-sm font-semibold text-ink flex items-center gap-2"><Users className="w-4 h-4 text-brand" />{t("trainer_batches.roster")}</h2>
                <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder={t("trainer_batches.search")} data-testid="roster-search"
                  className="px-2.5 py-1.5 border border-line rounded-tile text-xs" />
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs" data-testid="roster-table">
                  <thead className="text-muted bg-surface-2">
                    <tr>
                      <th className="text-left font-semibold px-3 py-2">{t("trainer_batches.student")}</th>
                      <th className="text-left font-semibold px-3 py-2">{t("trainer_batches.readiness")}</th>
                      <th className="text-left font-semibold px-3 py-2">{t("trainer_batches.attendance")}</th>
                      <th className="text-left font-semibold px-3 py-2">{t("trainer_batches.flags")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {shown?.map((s) => (
                      <tr key={s.id} className="border-t border-line-soft" data-testid="roster-row">
                        <td className="px-3 py-2">
                          <Link href={`/trainer/students/${s.id}`} className="font-semibold text-brand hover:underline">{s.name}</Link>
                          <div className="text-caption text-muted">{s.register_no}{s.pending_roster_request ? ` · ${t("trainer_batches.request_pending")}` : ""}</div>
                        </td>
                        <td className="px-3 py-2">{s.readiness_score} <span className={`ml-1 px-1.5 py-0.5 rounded-full text-caption font-semibold ${BAND[s.readiness_band] || ""}`}>{s.readiness_band}</span></td>
                        <td className="px-3 py-2">{s.attendance_pct}%</td>
                        <td className="px-3 py-2">{s.open_flags > 0 ? <span className="inline-flex items-center gap-1 text-warning font-semibold"><AlertTriangle className="w-3.5 h-3.5" />{s.open_flags}</span> : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
