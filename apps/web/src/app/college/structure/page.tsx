"use client";

/** Screen 03 · Branches and batches (college admin). Spec: docs/screens/03-branches-and-batches.md */
import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { API_BASE, ApiError, authHeaders, fetchApi } from "@/lib/api";
import { ArrowUpCircle, FileUp, GitBranch, Plus, UserCheck } from "lucide-react";

interface BatchRow { id: string; short_name: string; name: string; semester: number; academic_year: string; track: string; students: number; trainers: { trainer_id: string; name: string; role: string }[] }
interface BranchRow { id: string; name: string; code: string; track: string; hod_name: string | null; batches: BatchRow[] }
interface Structure { students_total: number; unassigned_students: number; branches: BranchRow[] }
interface ImportResult { dry_run: boolean; can_import?: boolean; imported?: boolean; summary: { rows: number; errors: number; new: number; updated: number; parents_linked: number }; errors: { row: number; register_no: string; error: string }[] }

function currentYear(): string {
  const d = new Date();
  const start = d.getMonth() >= 5 ? d.getFullYear() : d.getFullYear() - 1;
  return `${start}-${String((start + 1) % 100).padStart(2, "0")}`;
}

export default function CollegeStructurePage() {
  const { t } = useLanguage();
  const [data, setData] = useState<Structure | null>(null);
  const [trainers, setTrainers] = useState<{ id: string; name: string }[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [branchForm, setBranchForm] = useState({ name: "", code: "", track: "Software Engineering" });
  const [batchForm, setBatchForm] = useState({ branch_id: "", short_name: "", semester: "5", academic_year: currentYear() });
  const [mapFor, setMapFor] = useState<string | null>(null);
  const [mapForm, setMapForm] = useState({ trainer_id: "", role: "primary" });
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, tr] = await Promise.all([
        fetchApi<Structure>("/college/structure"),
        fetchApi<{ trainers: { id: string; name: string }[] }>("/college/trainers"),
      ]);
      setData(s);
      setTrainers(tr.trainers);
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("structure.load_failed"));
    }
  }, [t]);

  useEffect(() => { load(); }, [load]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("structure.save_failed"));
    } finally {
      setBusy(false);
    }
  };

  const addBranch = (e: React.FormEvent) => {
    e.preventDefault();
    if (branchForm.name.trim().length < 2 || !/^[A-Za-z0-9&]{2,16}$/.test(branchForm.code.trim())) return setError(t("structure.err_branch"));
    run(async () => {
      await fetchApi("/college/branches", { method: "POST", body: JSON.stringify({ ...branchForm, code: branchForm.code.trim() }) });
      setBranchForm({ name: "", code: "", track: branchForm.track });
    });
  };

  const addBatch = (e: React.FormEvent) => {
    e.preventDefault();
    const branchId = batchForm.branch_id || data?.branches[0]?.id || "";
    if (!branchId || batchForm.short_name.trim().length < 2) return setError(t("structure.err_batch"));
    run(async () => {
      await fetchApi("/college/batches", { method: "POST", body: JSON.stringify({ ...batchForm, branch_id: branchId, semester: Number(batchForm.semester) }) });
      setBatchForm({ ...batchForm, short_name: "" });
    });
  };

  const mapTrainer = (batchId: string) => {
    const trainerId = mapForm.trainer_id || trainers[0]?.id;
    if (!trainerId) return;
    run(async () => {
      await fetchApi(`/college/batches/${batchId}/trainers`, { method: "POST", body: JSON.stringify({ trainer_id: trainerId, role: mapForm.role }) });
      setMapFor(null);
    });
  };

  const promote = (b: BatchRow) => {
    if (!window.confirm(t("structure.promote_confirm").replace("{batch}", b.short_name).replace("{sem}", String(b.semester + 1)))) return;
    run(async () => { await fetchApi(`/college/batches/${b.id}/promote`, { method: "POST" }); });
  };

  const upload = async (dryRun: boolean) => {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const body = new FormData();
      body.append("file", file);
      // multipart: let the browser set Content-Type (fetchApi forces JSON)
      const res = await fetch(`${API_BASE}/college/students/import?dry_run=${dryRun}`, { method: "POST", body, headers: authHeaders() });
      const json = await res.json();
      if (!res.ok) throw new ApiError(res.status, typeof json.detail === "string" ? json.detail : t("structure.import_failed"));
      setResult(json);
      if (!dryRun) await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : t("structure.import_failed"));
    } finally {
      setBusy(false);
    }
  };

  const inputCls = "w-full px-2.5 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg text-xs";

  return (
    <RoleGuard allowedRoles={["college"]}>
      <AppShell pageTitle={t("structure.title")}>
        <div className="p-4 md:p-6 space-y-4 max-w-6xl">
          <p className="text-xs text-[#64748B]">{t("structure.subtitle")}</p>
          {error && <p className="text-xs text-red-600" role="alert" data-testid="structure-error">{error}</p>}

          {data && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-white rounded-xl border border-[#E2E8F0] p-3"><div className="text-[11px] text-[#64748B]">{t("structure.branches")}</div><div className="text-xl font-black" data-testid="count-branches">{data.branches.length}</div></div>
              <div className="bg-white rounded-xl border border-[#E2E8F0] p-3"><div className="text-[11px] text-[#64748B]">{t("structure.batches")}</div><div className="text-xl font-black">{data.branches.reduce((n, b) => n + b.batches.length, 0)}</div></div>
              <div className="bg-white rounded-xl border border-[#E2E8F0] p-3"><div className="text-[11px] text-[#64748B]">{t("structure.students")}</div><div className="text-xl font-black" data-testid="count-students">{data.students_total}</div></div>
              <div className="bg-white rounded-xl border border-[#E2E8F0] p-3"><div className="text-[11px] text-[#64748B]">{t("structure.unassigned")}</div><div className="text-xl font-black">{data.unassigned_students}</div></div>
            </div>
          )}

          {data && data.branches.length === 0 && (
            <div className="bg-white rounded-xl border border-dashed border-[#CBD5E1] p-6 text-center text-xs text-[#64748B]" data-testid="structure-empty">{t("structure.empty")}</div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <form onSubmit={addBranch} noValidate className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-2" data-testid="branch-form">
              <h2 className="text-sm font-black text-[#0F1F3A] flex items-center gap-2"><GitBranch className="w-4 h-4 text-[#2B5CD0]" />{t("structure.add_branch")}</h2>
              <div className="grid grid-cols-3 gap-2">
                <input className={`${inputCls} col-span-2`} placeholder={t("structure.branch_name")} value={branchForm.name} data-testid="branch-name" onChange={(e) => setBranchForm({ ...branchForm, name: e.target.value })} />
                <input className={inputCls} placeholder={t("structure.branch_code")} value={branchForm.code} data-testid="branch-code" onChange={(e) => setBranchForm({ ...branchForm, code: e.target.value })} />
              </div>
              <button type="submit" disabled={busy} data-testid="branch-save" className="px-3 py-1.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50 inline-flex items-center gap-1"><Plus className="w-3.5 h-3.5" />{t("structure.add_branch")}</button>
            </form>

            <form onSubmit={addBatch} noValidate className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-2" data-testid="batch-form">
              <h2 className="text-sm font-black text-[#0F1F3A] flex items-center gap-2"><Plus className="w-4 h-4 text-[#2B5CD0]" />{t("structure.add_batch")}</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                <select className={inputCls} value={batchForm.branch_id} data-testid="batch-branch" onChange={(e) => setBatchForm({ ...batchForm, branch_id: e.target.value })} aria-label={t("structure.branch_name")}>
                  {data?.branches.map((b) => <option key={b.id} value={b.id}>{b.code}</option>)}
                </select>
                <input className={inputCls} placeholder={t("structure.batch_name")} value={batchForm.short_name} data-testid="batch-name" onChange={(e) => setBatchForm({ ...batchForm, short_name: e.target.value })} />
                <select className={inputCls} value={batchForm.semester} data-testid="batch-semester" onChange={(e) => setBatchForm({ ...batchForm, semester: e.target.value })} aria-label={t("structure.semester")}>
                  {[2, 3, 4, 5, 6, 7].map((s) => <option key={s} value={s}>{t("structure.sem")} {s}</option>)}
                </select>
                <input className={inputCls} value={batchForm.academic_year} data-testid="batch-year" onChange={(e) => setBatchForm({ ...batchForm, academic_year: e.target.value })} aria-label={t("structure.year")} />
              </div>
              <button type="submit" disabled={busy || !data?.branches.length} data-testid="batch-save" className="px-3 py-1.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-50">{t("structure.add_batch")}</button>
            </form>
          </div>

          {data?.branches.map((br) => (
            <section key={br.id} className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-2" data-testid={`branch-${br.code}`}>
              <h2 className="text-sm font-black text-[#0F1F3A]">{br.name} <span className="text-[#64748B] font-mono font-normal">{br.code}</span></h2>
              {br.batches.length === 0 && <p className="text-xs text-[#64748B]">{t("structure.no_batches")}</p>}
              <ul className="divide-y divide-[#F1F5F9]">
                {br.batches.map((b) => (
                  <li key={b.id} className="py-2 text-xs flex flex-wrap items-center justify-between gap-2" data-testid={`batch-${b.short_name}`}>
                    <div>
                      <span className="font-bold">{b.short_name}</span> · {t("structure.sem")} {b.semester} · {b.academic_year} · <span data-testid="batch-students">{b.students}</span> {t("structure.students").toLowerCase()}
                      <div className="text-[11px] text-[#64748B]">
                        {b.trainers.length ? b.trainers.map((tr) => `${tr.name} (${t(`structure.role_${tr.role}`)})`).join(", ") : t("structure.no_trainer")}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {mapFor === b.id ? (
                        <>
                          <select className="px-2 py-1 border border-[#E2E8F0] rounded text-xs" value={mapForm.trainer_id} data-testid="map-trainer" onChange={(e) => setMapForm({ ...mapForm, trainer_id: e.target.value })} aria-label={t("structure.trainer")}>
                            {trainers.map((tr) => <option key={tr.id} value={tr.id}>{tr.name}</option>)}
                          </select>
                          <select className="px-2 py-1 border border-[#E2E8F0] rounded text-xs" value={mapForm.role} onChange={(e) => setMapForm({ ...mapForm, role: e.target.value })} aria-label={t("structure.role")}>
                            <option value="primary">{t("structure.role_primary")}</option>
                            <option value="substitute">{t("structure.role_substitute")}</option>
                          </select>
                          <button type="button" disabled={busy} onClick={() => mapTrainer(b.id)} data-testid="map-save" className="px-2.5 py-1 bg-[#2B5CD0] text-white font-bold rounded">{t("structure.map")}</button>
                        </>
                      ) : (
                        <button type="button" disabled={!trainers.length} onClick={() => { setMapFor(b.id); setMapForm({ trainer_id: trainers[0]?.id || "", role: "primary" }); }} data-testid="map-open"
                          className="px-2.5 py-1 border border-[#CBD5E1] rounded font-bold inline-flex items-center gap-1 disabled:opacity-40"><UserCheck className="w-3.5 h-3.5" />{t("structure.map_trainer")}</button>
                      )}
                      <button type="button" disabled={busy || b.semester >= 7} onClick={() => promote(b)} data-testid="promote"
                        className="px-2.5 py-1 border border-[#CBD5E1] rounded font-bold inline-flex items-center gap-1 disabled:opacity-40"><ArrowUpCircle className="w-3.5 h-3.5" />{t("structure.promote")}</button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ))}

          <section className="bg-white rounded-xl border border-[#E2E8F0] p-4 space-y-3" data-testid="import-section">
            <h2 className="text-sm font-black text-[#0F1F3A] flex items-center gap-2"><FileUp className="w-4 h-4 text-[#2B5CD0]" />{t("structure.import_title")}</h2>
            <p className="text-[11px] text-[#64748B]">{t("structure.import_help")} <code className="font-mono">register_no,name,email,phone,branch_code,batch,semester,parent_name,parent_phone</code></p>
            <div className="flex flex-wrap items-center gap-2">
              <input type="file" accept=".csv,text/csv" data-testid="import-file" onChange={(e) => { setFile(e.target.files?.[0] || null); setResult(null); }} className="text-xs" />
              <button type="button" disabled={!file || busy} onClick={() => upload(true)} data-testid="import-check" className="px-3 py-1.5 border border-[#CBD5E1] text-xs font-bold rounded-lg disabled:opacity-40">{t("structure.check_file")}</button>
              <button type="button" disabled={!file || busy || !result?.can_import} onClick={() => upload(false)} data-testid="import-run" className="px-3 py-1.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-lg disabled:opacity-40">{t("structure.import")}</button>
            </div>
            {result && (
              <div className="text-xs space-y-1" data-testid="import-result">
                <p className={result.imported ? "text-[#166534] font-bold" : "text-[#0F1F3A]"}>
                  {result.imported ? t("structure.imported") : t("structure.checked")}{" "}
                  {t("structure.summary").replace("{new}", String(result.summary.new)).replace("{updated}", String(result.summary.updated))
                    .replace("{parents}", String(result.summary.parents_linked)).replace("{errors}", String(result.summary.errors))}
                </p>
                {result.errors.length > 0 && (
                  <ul className="text-red-700 space-y-0.5" data-testid="import-errors">
                    {result.errors.map((er) => <li key={er.row}>{t("structure.row")} {er.row} ({er.register_no || "—"}): {er.error}</li>)}
                  </ul>
                )}
              </div>
            )}
          </section>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
