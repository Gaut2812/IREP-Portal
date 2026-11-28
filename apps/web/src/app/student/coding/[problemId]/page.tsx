"use client";

import React, { useState, useEffect, use, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { MonacoEditorWrapper } from "@/components/MonacoEditorWrapper";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi } from "@/lib/api";
import {
  Play,
  Send,
  Bot,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  MessageSquareQuote,
  RefreshCw,
  Code2,
  HelpCircle,
  ArrowLeft,
  ChevronDown,
  Clock,
  Cpu,
  Terminal,
  FlaskConical,
  Loader2,
  TrendingUp,
  Zap,
  BookOpen,
  ChevronRight,
  ChevronLeft,
  X,
  Search,
  Trophy,
  Layers,
  ArrowRight,
  Maximize2,
  Minimize2,
  RotateCcw,
  Map as MapIcon,
  AArrowDown,
  AArrowUp
} from "lucide-react";
import { TerminalPanel } from "@/components/coding/TerminalPanel";
import Link from "next/link";

interface TestCaseResult {
  name: string;
  status: string;
  time_ms?: number;
  error?: string;
  input_data?: string;
  expected_output?: string;
  actual_output?: string;
  stdout?: string;
}

interface ProblemNavItem {
  id: string;
  title: string;
  difficulty: string;
  topic: string;
  company_tags?: string;
  week_info: string;
  is_solved?: boolean;
  curriculum_index?: number;
}

interface ProblemData {
  id: string;
  title: string;
  difficulty: string;
  topic: string;
  company_tags: string;
  week_info: string;
  statement: string;
  example_input: string;
  example_output: string;
  constraints: string;
  starter_codes: Record<string, string>;
  starter_code: string;
  io_mode?: "function" | "stdio";
  judged_languages?: string[];
  trainer_notes: string;
  trainer_author: string;
  prev_problem?: { id: string; title: string; week_info?: string } | null;
  next_problem?: { id: string; title: string; week_info?: string } | null;
  curriculum_index?: number;
  total_problems?: number;
  ai_reviewer: {
    tag: string;
    hints: Array<{ type: string; text: string; color: string }>;
    revealed_hints: string[];
    hints_used: number;
    max_hints: number;
    rules_note: string;
  };
  last_submission?: {
    status: string;
    runtime_ms: number;
    memory_mb: number;
    tests_passed: number;
    tests_total: number;
    submitted_at: string;
  } | null;
}

interface ReviewResult {
  overall_evaluation: string;
  time_complexity: string;
  space_complexity: string;
  good_practices: string[];
  try_next: string;
  interview_tip: string;
  code_smells: string[];
  detected_patterns: string[];
  analysis_duration_ms?: number;
  engine?: string;
}

const TOOL = "p-1.5 rounded-tile text-line-strong hover:text-white hover:bg-[#2D3748] transition-colors";

export default function CodingLabPage({ params }: { params: Promise<{ problemId: string }> }) {
  const resolvedParams = use(params);
  const problemId = resolvedParams.problemId || "prob_connected_components";
  const router = useRouter();
  const { t } = useLanguage();
  const fill = (k: string, v: Record<string, string | number>) =>
    Object.entries(v).reduce((acc, [kk, vv]) => acc.replace(`{${kk}}`, String(vv)), t(k));

  const [problem, setProblem] = useState<ProblemData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState<boolean>(false);

  // Editor states
  const [language, setLanguage] = useState<string>("python");
  const [code, setCode] = useState<string>("");
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // 20-Problem Curriculum Navigator Drawer state
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);
  const [allProblems, setAllProblems] = useState<ProblemNavItem[]>([]);
  const [selectedWeekFilter, setSelectedWeekFilter] = useState<string>("All");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Results state
  const [runResult, setRunResult] = useState<{
    status: string;
    runtime_ms?: number;
    memory_mb?: number;
    cases: TestCaseResult[];
    error_message?: string;
    is_submit?: boolean;
    tests_passed?: number;
    tests_total?: number;
    stdout?: string;
    next_problem?: { id: string; title: string; week_info?: string } | null;
  } | null>(null);

  // Terminal drawer state
  const [activeTab, setActiveTab] = useState<"cases" | "terminal">("cases");
  const [selectedCase, setSelectedCase] = useState<number>(0);

  // AI Review state
  const [isReviewing, setIsReviewing] = useState<boolean>(false);
  const [reviewResult, setReviewResult] = useState<ReviewResult | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [hintError, setHintError] = useState<string | null>(null);

  // Hints state
  const [hints, setHints] = useState<string[]>([]);
  const [hintsCount, setHintsCount] = useState<number>(1);
  const [isRequestingHint, setIsRequestingHint] = useState<boolean>(false);

  // Success celebration state
  const [showSuccessModal, setShowSuccessModal] = useState<boolean>(false);

  // Editor preferences (kept in this browser) and full screen
  const [fontSize, setFontSize] = useState<number>(14);
  const [minimap, setMinimap] = useState<boolean>(false);
  const [focusMode, setFocusMode] = useState<boolean>(false);
  const labRef = useRef<HTMLDivElement>(null);
  const languageRef = useRef(language);
  languageRef.current = language;

  useEffect(() => {
    try {
      const f = Number(localStorage.getItem("irep_editor_font"));
      if (f >= 11 && f <= 24) setFontSize(f);
      setMinimap(localStorage.getItem("irep_editor_minimap") === "1");
    } catch { /* private mode: defaults */ }
  }, []);
  const changeFont = (delta: number) => setFontSize((f) => {
    const next = Math.min(24, Math.max(11, f + delta));
    try { localStorage.setItem("irep_editor_font", String(next)); } catch { /* ignore */ }
    return next;
  });
  const toggleMinimap = () => setMinimap((m) => {
    try { localStorage.setItem("irep_editor_minimap", m ? "0" : "1"); } catch { /* ignore */ }
    return !m;
  });

  // Full screen: the editor and terminal fill the screen (browser full screen when allowed). Esc leaves it.
  useEffect(() => {
    const onChange = () => { if (!document.fullscreenElement) setFocusMode(false); };
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);
  useEffect(() => {
    if (!focusMode) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !document.fullscreenElement) setFocusMode(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [focusMode]);
  const toggleFocus = async () => {
    if (focusMode) {
      if (document.fullscreenElement) await document.exitFullscreen().catch(() => undefined);
      setFocusMode(false);
    } else {
      setFocusMode(true);
      await labRef.current?.requestFullscreen?.().catch(() => undefined);   // denied: the in-page full view still applies
    }
  };

  // Drafts: your code is kept per problem and language in this browser, so a reload or a language switch loses nothing
  const draftKey = useCallback((lang: string) => `irep_code:${problemId}:${lang}`, [problemId]);
  const readDraft = useCallback((lang: string): string | null => {
    try { return localStorage.getItem(draftKey(lang)); } catch { return null; }
  }, [draftKey]);
  const onCodeChange = (val: string) => {
    setCode(val);
    try { localStorage.setItem(draftKey(language), val); } catch { /* storage full or blocked */ }
  };
  const resetCode = () => {
    const starter = problem?.starter_codes?.[language] || problem?.starter_code || "";
    setCode(starter);
    try { localStorage.removeItem(draftKey(language)); } catch { /* ignore */ }
  };

  // Fetch all 20 problems list for drawer
  useEffect(() => {
    async function fetchCurriculumProblems() {
      try {
        const res = await fetchApi<{ total: number; problems: ProblemNavItem[] }>("/student/coding");
        if (res?.problems && Array.isArray(res.problems)) {
          setAllProblems(res.problems);
        } else {
          setAllProblems([]);
        }
      } catch (e) {
        setAllProblems([]);
      }
    }
    fetchCurriculumProblems();
  }, []);

  // Fetch problem data
  const loadProblem = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNotFound(false);
    setShowSuccessModal(false);
    try {
      const data = await fetchApi<ProblemData>(`/student/coding/${problemId}`);
      setProblem(data);
      const lang = languageRef.current;
      setCode(readDraft(lang) ?? (data.starter_codes?.[lang] || data.starter_code || ""));
      setHints(data.ai_reviewer?.revealed_hints || []);
      setHintsCount(data.ai_reviewer?.hints_used || 1);

      if (data.last_submission) {
        setRunResult({
          status: data.last_submission.status,
          runtime_ms: data.last_submission.runtime_ms,
          memory_mb: data.last_submission.memory_mb,
          is_submit: true,
          tests_passed: data.last_submission.tests_passed,
          tests_total: data.last_submission.tests_total,
          next_problem: data.next_problem,
          cases: [],
        });
      }
    } catch (err: any) {
      if (err?.message?.includes("404")) {
        setNotFound(true);
      } else {
        setError(err?.message || t("coding.error_title"));
        setProblem(null);
      }
    } finally {
      setLoading(false);
    }
  }, [problemId, readDraft]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    loadProblem();
  }, [loadProblem]);

  // Handle language switch
  const handleLanguageChange = (newLang: string) => {
    setLanguage(newLang);
    setCode(readDraft(newLang) ?? (problem?.starter_codes?.[newLang] || ""));
    // a language this problem's tests don't run in: the terminal is where its code runs
    if (problem?.judged_languages && !problem.judged_languages.includes(newLang)) setActiveTab("terminal");
  };
  const judged = !problem?.judged_languages || problem.judged_languages.includes(language);

  // Run sample cases
  const handleRun = async () => {
    setIsRunning(true);
    setActiveTab("cases");
    try {
      const res = await fetchApi<any>(`/student/coding/${problemId}/run`, {
        method: "POST",
        body: JSON.stringify({ code, language })
      });
      setRunResult({
        status: res.status,
        runtime_ms: res.runtime_ms,
        memory_mb: res.memory_mb,
        cases: res.cases || [],
        error_message: res.error_message,
        is_submit: false,
        stdout: res.stdout || res.stdout_log || `# Execution finished\nStatus: ${res.status}\nRuntime: ${res.runtime_ms} ms`
      });
    } catch (err: any) {
      setRunResult({
        status: "Error",
        is_submit: false,
        cases: [],
        error_message: `${t("coding.request_failed")} (${err?.message || "network"})`,
      });
    } finally {
      setIsRunning(false);
    }
  };

  // Submit against hidden tests
  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      const res = await fetchApi<any>(`/student/coding/${problemId}/submit`, {
        method: "POST",
        body: JSON.stringify({ code, language })
      });
      setRunResult({
        status: res.status,
        runtime_ms: res.runtime_ms,
        memory_mb: res.memory_mb,
        cases: res.cases || [],
        is_submit: true,
        tests_passed: res.tests_passed,
        tests_total: res.tests_total,
        stdout: res.stdout || `# Official Submission Evaluated\nStatus: ${res.status}\nPassed: ${res.tests_passed}/${res.tests_total} tests`,
        next_problem: res.next_problem || problem?.next_problem
      });

      if (res.status === "Accepted") {
        setShowSuccessModal(true);
      }
    } catch (err: any) {
      setRunResult({
        status: "Error",
        is_submit: true,
        cases: [],
        error_message: `${t("coding.submit_failed")} (${err?.message || "network"})`,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  // AI Code Review
  const handleRunReview = async () => {
    if (!code.trim()) return;
    setIsReviewing(true);
    setReviewError(null);
    try {
      const res = await fetchApi<ReviewResult>(`/student/coding/${problemId}/review`, {
        method: "POST",
        body: JSON.stringify({ code, language })
      });
      setReviewResult(res);
    } catch (e: any) {
      setReviewResult(null);
      setReviewError(`${t("coding.review_failed")} (${e?.message || "network"})`);
    } finally {
      setIsReviewing(false);
    }
  };

  // Request next AI hint
  const handleRequestHint = async () => {
    setIsRequestingHint(true);
    setHintError(null);
    try {
      const res = await fetchApi<any>(`/student/coding/${problemId}/hint`, {
        method: "POST",
        body: JSON.stringify({ current_count: hintsCount })
      });
      // functional updates: the click can land before the initial load settles
      if (res.hint) {
        setHints((prev) => (prev.includes(res.hint) ? prev : [...prev, res.hint]));
        if (res.hints_used) setHintsCount(res.hints_used);
      }
    } catch (err: any) {
      setHintError(`${t("coding.hint_failed")} (${err?.message || "network"})`);
    } finally {
      setIsRequestingHint(false);
    }
  };

  // Advance to next problem
  const handleGoToNextProblem = () => {
    const target = runResult?.next_problem || problem?.next_problem;
    if (target?.id) {
      setShowSuccessModal(false);
      router.push(`/student/coding/${target.id}`);
    }
  };

  // Filter problems for the drawer
  const filteredProblems = allProblems.filter((p) => {
    const matchesWeek = selectedWeekFilter === "All" || p.week_info?.includes(`Week ${selectedWeekFilter}`);
    const matchesSearch = searchQuery === "" ||
      p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.topic.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesWeek && matchesSearch;
  });

  const solvedCount = allProblems.filter((p) => p.is_solved).length;
  const activeCaseData = runResult?.cases?.[selectedCase];
  const nextTarget = runResult?.next_problem || problem?.next_problem;

  return (
    <RoleGuard allowedRoles={["student", "trainer"]}>
      <AppShell pageTitle={t("coding.title") || "Coding Lab"}>
        {/* LOADING SKELETON */}
        {loading && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 h-[calc(100vh-120px)] animate-pulse">
            <div className="lg:col-span-4 bg-white rounded-card border border-line p-5 space-y-4">
              <div className="h-6 w-1/3 bg-slate-200 rounded"></div>
              <div className="h-8 w-3/4 bg-slate-200 rounded"></div>
              <div className="h-32 bg-slate-100 rounded-card"></div>
              <div className="h-20 bg-slate-100 rounded-card"></div>
            </div>
            <div className="lg:col-span-5 flex flex-col gap-4">
              <div className="flex-1 bg-slate-800 rounded-card"></div>
              <div className="h-44 bg-white rounded-card border border-line"></div>
            </div>
            <div className="lg:col-span-3 bg-white rounded-card border border-line p-4 space-y-4">
              <div className="h-6 w-1/2 bg-slate-200 rounded"></div>
              <div className="h-20 bg-blue-50 rounded-card"></div>
              <div className="h-20 bg-amber-50 rounded-card"></div>
            </div>
          </div>
        )}

        {/* 404 NOT FOUND STATE */}
        {!loading && notFound && (
          <div className="flex items-center justify-center min-h-[60vh]">
            <div className="max-w-md w-full bg-white rounded-card border border-line p-8 shadow-card text-center space-y-4">
              <div className="w-14 h-14 mx-auto rounded-full bg-warning-soft flex items-center justify-center text-warning">
                <AlertCircle className="w-8 h-8" />
              </div>
              <h2 className="text-xl font-semibold text-ink">
                {t("coding.not_found_title") || "Problem Not Found"}
              </h2>
              <p className="text-sm text-muted">
                {t("coding.not_found_desc") || "The requested coding problem could not be found for your college tenant."}
              </p>
              <div className="pt-2 flex justify-center gap-2">
                <button
                  onClick={() => setIsDrawerOpen(true)}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-teal hover:bg-teal-hover text-white text-xs font-semibold rounded-card shadow-card cursor-pointer transition-all"
                >
                  <Layers className="w-3.5 h-3.5" />
                  <span>{t("coding.browse_problems")}</span>
                </button>
                <Link
                  href="/student"
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-brand hover:bg-brand-hover text-white text-xs font-semibold rounded-card shadow-card transition-all"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>{t("coding.back_to_dashboard") || "Dashboard"}</span>
                </Link>
              </div>
            </div>
          </div>
        )}

        {/* ERROR STATE WITH RETRY */}
        {!loading && error && !problem && (
          <div className="flex items-center justify-center min-h-[60vh]">
            <div className="max-w-md w-full bg-white rounded-card border border-danger-soft p-8 shadow-card text-center space-y-4">
              <div className="w-14 h-14 mx-auto rounded-full bg-danger-soft flex items-center justify-center text-danger">
                <AlertCircle className="w-8 h-8" />
              </div>
              <h2 className="text-xl font-semibold text-ink">
                {t("coding.error_title") || "Failed to load coding challenge"}
              </h2>
              <p className="text-sm text-muted">{error}</p>
              <div className="pt-2">
                <button
                  onClick={loadProblem}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-teal hover:bg-teal-hover text-white text-xs font-semibold rounded-card shadow-card transition-all cursor-pointer"
                >
                  <RefreshCw className="w-4 h-4" />
                  <span>{t("coding.retry") || "Retry"}</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* LOADED 3-COLUMN CONTENT */}
        {!loading && problem && (
          <div ref={labRef} data-testid="coding-lab" data-focus={focusMode ? "true" : "false"}
            className={focusMode ? "fixed inset-0 z-40 bg-canvas p-3 grid grid-cols-1 gap-3" : "grid grid-cols-1 lg:grid-cols-12 gap-5 h-[calc(100vh-120px)]"}>

            {/* LEFT COLUMN: Problem Statement (4 cols) */}
            <div className={`${focusMode ? "hidden" : ""} lg:col-span-4 bg-white rounded-card border border-line shadow-card flex flex-col justify-between overflow-hidden`}>
              <div className="p-5 overflow-y-auto space-y-4">
                {/* Curriculum Problem Switcher Bar */}
                <div className="flex items-center justify-between pb-3 border-b border-line">
                  <button
                    onClick={() => setIsDrawerOpen(true)}
                    data-testid="problem-switcher-button"
                    className="flex items-center gap-1.5 px-2.5 py-1 bg-surface-2 hover:bg-slate-100 text-ink text-xs font-semibold rounded-tile border border-line-strong transition-all cursor-pointer"
                    title={t("coding.browse_title")}
                  >
                    <Layers className="w-3.5 h-3.5 text-brand" />
                    <span>{fill("coding.problem_n_of", { n: problem.curriculum_index ?? 1, total: problem.total_problems ?? allProblems.length })}</span>
                    <ChevronDown className="w-3 h-3 text-muted" />
                  </button>

                  <div className="flex items-center gap-1">
                    {problem.prev_problem && (
                      <Link
                        href={`/student/coding/${problem.prev_problem.id}`}
                        data-testid="prev-problem-button"
                        className="p-1 rounded hover:bg-slate-100 text-muted hover:text-ink transition-colors"
                        title={`Previous: ${problem.prev_problem.title}`}
                      >
                        <ChevronLeft className="w-4 h-4" />
                      </Link>
                    )}
                    {problem.next_problem && (
                      <Link
                        href={`/student/coding/${problem.next_problem.id}`}
                        data-testid="next-problem-button-header"
                        className="p-1 rounded hover:bg-slate-100 text-muted hover:text-ink transition-colors"
                        title={`Next: ${problem.next_problem.title}`}
                      >
                        <ChevronRight className="w-4 h-4" />
                      </Link>
                    )}
                  </div>
                </div>

                {/* Tag Chips */}
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap gap-2">
                    <span className="chip-amber">{problem.difficulty}</span>
                    <span className="chip-blue">{problem.topic}</span>
                    {problem.company_tags && <span className="chip-purple">{t("coding.asked")} {problem.company_tags}</span>}
                  </div>
                </div>

                {/* Title */}
                <h2 className="text-base font-semibold text-ink">
                  {problem.title}
                </h2>

                {/* Description */}
                <p className="text-xs text-ink-soft leading-relaxed whitespace-pre-line">
                  {problem.statement}
                </p>

                {/* Example Box */}
                <div className="bg-surface-2 border border-line rounded-card p-3.5 space-y-2 text-xs">
                  <div className="font-semibold text-ink">{t("coding.example") || "Example"}:</div>
                  <div className="font-mono text-caption text-ink-soft space-y-0.5">
                    <div><span className="text-muted">{t("coding.input")}:</span> {problem.example_input}</div>
                    <div><span className="text-muted">{t("coding.output")}:</span> {problem.example_output}</div>
                  </div>
                </div>

                {/* Constraints */}
                <div className="space-y-1.5 pt-2">
                  <div className="text-xs font-semibold text-ink">{t("coding.constraints") || "Constraints"}:</div>
                  <pre className="font-mono text-caption text-muted whitespace-pre-wrap leading-relaxed bg-surface-2 p-2.5 rounded-tile border border-line">
                    {problem.constraints}
                  </pre>
                </div>
              </div>

              {/* Footer: the week this problem belongs to (the list opens from the switcher at the top) */}
              {problem.week_info && (
                <div className="p-3 bg-surface-2 border-t border-line text-caption font-semibold text-muted">{problem.week_info}</div>
              )}
            </div>

            {/* MIDDLE COLUMN: Code Editor + Test Results / Terminal Drawer (5 cols) */}
            <div className={`${focusMode ? "h-full min-h-0" : "lg:col-span-5"} flex flex-col gap-4 overflow-hidden`}>
              {/* Editor Container */}
              <div className="flex-1 bg-[#1B2236] rounded-card border border-[#2D3748] shadow-card flex flex-col overflow-hidden">
                {/* Editor Header Bar */}
                <div className="h-10 bg-[#141A29] px-4 flex items-center justify-between border-b border-[#2D3748] flex-shrink-0">
                  <div className="flex items-center gap-2">
                    <Code2 className="w-3.5 h-3.5 text-teal" />
                    <div className="relative inline-block">
                      <select
                        value={language}
                        onChange={(e) => handleLanguageChange(e.target.value)}
                        className="bg-[#1E293B] text-line-strong text-xs font-mono px-2.5 py-1 pr-6 rounded border border-ink-soft appearance-none focus:outline-none cursor-pointer"
                        data-testid="language-selector"
                      >
                        {([["python", "solution.py (Python 3)"], ["java", "Main.java (Java)"], ["cpp", "solution.cpp (C++)"], ["javascript", "solution.js (Node.js)"]] as const).map(([v, label]) => (
                          <option key={v} value={v}>{label}{problem.judged_languages && !problem.judged_languages.includes(v) ? ` · ${t("coding.terminal_only")}` : ""}</option>
                        ))}
                      </select>
                      <ChevronDown className="w-3 h-3 text-subtle absolute right-2 top-2 pointer-events-none" />
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <div className="hidden sm:flex items-center gap-0.5 mr-1" role="group" aria-label={t("coding.editor_tools")}>
                      <button type="button" onClick={() => changeFont(-1)} className={TOOL} aria-label={t("coding.font_smaller")} title={t("coding.font_smaller")} data-testid="font-smaller"><AArrowDown className="w-4 h-4" /></button>
                      <span className="text-caption font-mono text-subtle w-6 text-center" data-testid="font-size">{fontSize}</span>
                      <button type="button" onClick={() => changeFont(1)} className={TOOL} aria-label={t("coding.font_larger")} title={t("coding.font_larger")} data-testid="font-larger"><AArrowUp className="w-4 h-4" /></button>
                      <button type="button" onClick={toggleMinimap} aria-pressed={minimap} className={`${TOOL} ${minimap ? "text-teal" : ""}`} aria-label={t("coding.minimap")} title={t("coding.minimap")} data-testid="minimap-toggle"><MapIcon className="w-4 h-4" /></button>
                      <button type="button" onClick={resetCode} className={TOOL} aria-label={t("coding.reset_code")} title={t("coding.reset_code")} data-testid="reset-code"><RotateCcw className="w-4 h-4" /></button>
                    </div>
                    <button type="button" onClick={toggleFocus} className={TOOL} aria-pressed={focusMode}
                      aria-label={focusMode ? t("coding.exit_full_screen") : t("coding.full_screen")} title={focusMode ? t("coding.exit_full_screen") : t("coding.full_screen")} data-testid="full-screen">
                      {focusMode ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
                    </button>
                    <button
                      onClick={handleRun}
                      disabled={isRunning || isSubmitting || !judged}
                      title={judged ? undefined : t("coding.not_judged_lang")}
                      className="flex items-center gap-1.5 px-3 py-1 bg-transparent border border-ink-soft hover:bg-[#2D3748] text-white text-xs font-semibold rounded-tile transition-all cursor-pointer disabled:opacity-50"
                      data-testid="run-button"
                    >
                      {isRunning ? (
                        <RefreshCw className="w-3 h-3 text-teal animate-spin" />
                      ) : (
                        <Play className="w-3 h-3 text-teal" />
                      )}
                      <span>{isRunning ? (t("coding.running") || "Running...") : (t("coding.run") || "Run")}</span>
                    </button>
                    <button
                      onClick={handleSubmit}
                      disabled={isRunning || isSubmitting || !judged}
                      title={judged ? undefined : t("coding.not_judged_lang")}
                      className="flex items-center gap-1.5 px-3.5 py-1 bg-teal hover:bg-teal-hover text-white text-xs font-semibold rounded-tile shadow-card transition-all cursor-pointer disabled:opacity-50"
                      data-testid="submit-button"
                    >
                      {isSubmitting ? (
                        <RefreshCw className="w-3 h-3 animate-spin" />
                      ) : (
                        <Send className="w-3 h-3" />
                      )}
                      <span>{isSubmitting ? (t("coding.submitting") || "Submitting...") : (t("coding.submit") || "Submit")}</span>
                    </button>
                  </div>
                </div>

                {/* Monaco Code Editor Area */}
                <div className="flex-1 overflow-hidden relative">
                  <MonacoEditorWrapper
                    value={code}
                    language={language}
                    onChange={onCodeChange}
                    fontSize={fontSize}
                    minimap={minimap}
                  />
                </div>
              </div>

              {/* Test Results + Terminal Drawer */}
              <div className={`${focusMode ? "h-72" : "h-56"} bg-white rounded-card border border-line shadow-card flex flex-col flex-shrink-0 overflow-hidden`} data-testid="test-results-drawer">
                {/* Drawer Header with Dual Tabs */}
                <div className="flex items-center justify-between px-4 py-2 border-b border-line flex-shrink-0">
                  <div className="flex items-center gap-3">
                    {/* Tab: Test Cases */}
                    <button
                      onClick={() => setActiveTab("cases")}
                      data-testid="tab-test-cases"
                      className={`flex items-center gap-1.5 text-xs font-semibold pb-1 border-b-2 transition-all cursor-pointer ${
                        activeTab === "cases"
                          ? "border-brand text-brand"
                          : "border-transparent text-muted hover:text-ink"
                      }`}
                    >
                      <FlaskConical className="w-3.5 h-3.5" />
                      <span>{t("coding.test_results") || "Test Results"}</span>
                      {runResult?.status && (
                        <span className={`text-caption font-semibold px-1.5 py-0.5 rounded-full ml-1 ${
                          runResult.status === "Passed" || runResult.status === "Accepted"
                            ? "bg-success-soft text-success"
                            : "bg-danger-soft text-danger"
                        }`}>
                          {runResult.status}
                        </span>
                      )}
                    </button>
                    {/* Tab: Terminal */}
                    <button
                      onClick={() => setActiveTab("terminal")}
                      data-testid="tab-terminal"
                      className={`flex items-center gap-1.5 text-xs font-semibold pb-1 border-b-2 transition-all cursor-pointer ${
                        activeTab === "terminal"
                          ? "border-success-fill text-success-fill"
                          : "border-transparent text-muted hover:text-ink"
                      }`}
                    >
                      <Terminal className="w-3.5 h-3.5" />
                      <span>{t("coding.terminal") || "Terminal"}</span>
                    </button>
                  </div>

                  <div className="flex items-center gap-3 text-caption font-mono text-muted">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3 text-brand" />
                      {t("coding.runtime") || "Runtime"} {runResult?.runtime_ms ?? "-"} ms
                    </span>
                    <span className="flex items-center gap-1">
                      <Cpu className="w-3 h-3 text-violet" />
                      {t("coding.memory") || "Memory"} {runResult?.memory_mb ?? "-"} MB
                    </span>
                  </div>
                </div>

                {/* Drawer Body */}
                <div className="flex-1 overflow-hidden">
                  {/* TEST CASES TAB */}
                  {activeTab === "cases" && (
                    <div className="h-full flex flex-col p-3 gap-2 overflow-y-auto">
                      {!judged && <p className="text-caption text-warning" data-testid="not-judged-note">{t("coding.not_judged_lang")}</p>}
                      {/* a failed run shows its error AND which cases failed (it used to hide the cases) */}
                      {runResult?.error_message && (
                        <div className="p-2.5 rounded-tile bg-danger-faint border border-danger-line text-xs text-danger font-mono">
                          {runResult.error_message}
                        </div>
                      )}
                      {(runResult?.cases?.length ?? 0) > 0 || !runResult?.error_message ? (
                        <>
                          {/* Case Pills Row */}
                          <div className="flex flex-wrap gap-1.5">
                            {(runResult?.cases || []).map((c, i) => (
                              <button
                                key={i}
                                onClick={() => setSelectedCase(i)}
                                data-testid={`case-pill-${i}`}
                                className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-caption font-semibold cursor-pointer transition-all border ${
                                  selectedCase === i
                                    ? c.status === "Passed"
                                      ? "bg-success-soft border-success-line text-success ring-1 ring-success"
                                      : "bg-danger-soft border-danger-line text-danger ring-1 ring-danger"
                                    : c.status === "Passed"
                                      ? "bg-success-faint border-success-line text-success"
                                      : "bg-danger-faint border-danger-line text-danger"
                                }`}
                              >
                                {c.status === "Passed" ? (
                                  <CheckCircle2 className="w-3 h-3" />
                                ) : (
                                  <AlertCircle className="w-3 h-3" />
                                )}
                                <span>{c.name}</span>
                              </button>
                            ))}
                          </div>

                          {/* Case Detail — strictly public sample cases only */}
                          {activeCaseData && (activeCaseData.input_data || activeCaseData.expected_output) && (
                            <div className="flex gap-2 text-caption font-mono">
                              {activeCaseData.input_data && (
                                <div className="flex-1 min-w-0">
                                  <div className="text-caption font-semibold text-muted mb-0.5">{t("coding.input")}</div>
                                  <pre className="bg-surface-2 border border-line rounded p-1.5 text-ink-soft overflow-x-auto whitespace-pre-wrap">{activeCaseData.input_data}</pre>
                                </div>
                              )}
                              {activeCaseData.expected_output && (
                                <div className="flex-1 min-w-0">
                                  <div className="text-caption font-semibold text-muted mb-0.5">{t("coding.expected")}</div>
                                  <pre className="bg-success-faint border border-success-line rounded p-1.5 text-success overflow-x-auto">{activeCaseData.expected_output}</pre>
                                </div>
                              )}
                              {activeCaseData.actual_output && (
                                <div className="flex-1 min-w-0">
                                  <div className="text-caption font-semibold text-muted mb-0.5">{t("coding.output")}</div>
                                  <pre className={`border rounded p-1.5 overflow-x-auto ${
                                    activeCaseData.actual_output === activeCaseData.expected_output
                                      ? "bg-success-faint border-success-line text-success"
                                      : "bg-danger-faint border-danger-line text-danger"
                                  }`}>{activeCaseData.actual_output}</pre>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Result summary and next-problem action: counts come only from a real run or submission */}
                          {runResult && (
                          <div className={`text-xs font-semibold flex items-center justify-between mt-auto pt-1 ${runResult.status === "Accepted" || runResult.status === "Passed" ? "text-success" : "text-danger"}`}>
                            <div className="flex items-center gap-1.5">
                              {runResult.status === "Accepted" || runResult.status === "Passed" ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                              <span data-testid="result-summary">
                                {runResult.is_submit && runResult.tests_total != null
                                  ? `${runResult.tests_passed ?? 0} / ${runResult.tests_total} ${t("coding.hidden_passed")}`
                                  : fill("coding.samples_passed", { n: runResult.cases.filter((c) => c.status === "Passed").length, total: runResult.cases.length })}
                              </span>
                            </div>

                            {/* NEXT PROBLEM BUTTON (Shown when accepted) */}
                            {runResult?.status === "Accepted" && nextTarget ? (
                              <button
                                onClick={handleGoToNextProblem}
                                data-testid="next-problem-button"
                                className="inline-flex items-center gap-1.5 px-3 py-1 bg-success hover:bg-success text-white text-caption font-semibold rounded-tile shadow-card transition-all cursor-pointer animate-pulse"
                              >
                                <span>{fill("coding.next_problem_named", { title: nextTarget.title })}</span>
                                <ArrowRight className="w-3.5 h-3.5" />
                              </button>
                            ) : (
                              <span className="text-caption font-normal text-muted">
                                {runResult.is_submit ? t("coding.submission_recorded") : t("coding.sample_run_done")}
                              </span>
                            )}
                          </div>
                          )}
                          {/* a failed submission: Study Buddy explains it (hints, not the answer) */}
                          {runResult?.is_submit && runResult.status !== "Accepted" && runResult.status !== "Error" && (
                            <Link href={`/student/buddy?explain=${problemId}`} data-testid="explain-failure"
                              className="self-start inline-flex items-center gap-1.5 text-caption font-semibold text-brand hover:underline">
                              <Bot className="w-3.5 h-3.5" />{t("coding.ask_buddy_why")}
                            </Link>
                          )}
                          {!runResult && <p className="text-caption text-muted">{t("coding.results_empty")}</p>}
                        </>
                      ) : null}
                    </div>
                  )}

                  {/* TERMINAL TAB: run the code on your own input */}
                  {activeTab === "terminal" && (
                    <TerminalPanel problemId={problemId} code={code} language={language} t={t} />
                  )}
                </div>
              </div>
            </div>

            {/* RIGHT COLUMN: AI Code Reviewer + Trainer Notes (3 cols) */}
            <div className={`${focusMode ? "hidden" : ""} lg:col-span-3 bg-white rounded-card border border-line shadow-card p-4 flex flex-col justify-between overflow-y-auto space-y-4`}>
              <div className="space-y-4">
                {/* AI Reviewer Header */}
                <div className="flex items-center justify-between border-b border-line pb-3">
                  <div className="flex items-center gap-1.5">
                    <Bot className="w-4 h-4 text-brand" />
                    <h3 className="font-semibold text-xs text-ink">
                      {t("coding.ai_reviewer") || "AI Code Reviewer"}
                    </h3>
                  </div>
                  <span className="chip-purple text-caption">
                    {t("coding.future_skills") || "Future Skills"}
                  </span>
                </div>

                {/* AI Review Button */}
                <button
                  onClick={handleRunReview}
                  disabled={isReviewing || !code.trim()}
                  data-testid="run-ai-review-button"
                  className="w-full flex items-center justify-center gap-1.5 py-2 bg-brand hover:bg-brand-hover disabled:bg-subtle text-white text-xs font-semibold rounded-tile transition-all cursor-pointer disabled:cursor-not-allowed shadow-card"
                >
                  {isReviewing ? (
                    <><Loader2 className="w-3.5 h-3.5 animate-spin" /><span>{t("coding.analyzing")}</span></>
                  ) : (
                    <><Zap className="w-3.5 h-3.5" /><span>{t("coding.run_review") || "Analyze Code"}</span></>
                  )}
                </button>

                {reviewError && (
                  <div role="alert" data-testid="review-error" className="p-2.5 rounded-tile bg-danger-faint border border-danger-line text-caption text-danger">
                    {reviewError}
                  </div>
                )}

                {/* AI Review Results */}
                {reviewResult ? (
                  <div className="space-y-2">
                    {/* Complexity Badges */}
                    <div className="flex gap-2 text-caption">
                      <div className="flex-1 bg-success-faint border border-success-line rounded-tile p-2 text-center">
                        <div className="text-caption text-muted font-semibold flex items-center justify-center gap-1">
                          <TrendingUp className="w-2.5 h-2.5" />
                          {t("coding.time_complexity") || "Time Complexity"}
                        </div>
                        <div className="font-semibold text-success text-caption mt-0.5 leading-tight">{reviewResult.time_complexity}</div>
                      </div>
                      <div className="flex-1 bg-brand-soft border border-brand-line rounded-tile p-2 text-center">
                        <div className="text-caption text-muted font-semibold flex items-center justify-center gap-1">
                          <Cpu className="w-2.5 h-2.5" />
                          {t("coding.space_complexity") || "Space Complexity"}
                        </div>
                        <div className="font-semibold text-info text-caption mt-0.5 leading-tight">{reviewResult.space_complexity}</div>
                      </div>
                    </div>

                    {/* Good Practice (dynamic) */}
                    <div className="p-3 rounded-card bg-brand-soft border border-brand-line text-xs space-y-1" data-testid="ai-good-practice">
                      <div className="font-semibold text-info flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5" /> {t("coding.good_practice") || "Good Practice"}
                      </div>
                      {reviewResult.good_practices.slice(0, 2).map((p, i) => (
                        <p key={i} className="text-info text-caption leading-relaxed">{p}</p>
                      ))}
                    </div>

                    {/* Try Next (dynamic) */}
                    <div className="p-3 rounded-card bg-warning-soft border border-warning-line text-xs space-y-1">
                      <div className="font-semibold text-warning">{t("coding.try_next") || "Try next:"}</div>
                      <p className="text-warning text-caption leading-relaxed">{reviewResult.try_next}</p>
                    </div>

                    {/* Interview Tip (dynamic) */}
                    <div className="p-3 rounded-card bg-brand-soft border border-brand-line text-xs space-y-1">
                      <div className="font-semibold text-info">{t("coding.interview_tip") || "Interview tip:"}</div>
                      <p className="text-info text-caption leading-relaxed font-mono">{reviewResult.interview_tip}</p>
                    </div>

                    {/* Code Smells (if any) */}
                    {reviewResult.code_smells && reviewResult.code_smells.length > 0 && (
                      <div className="p-2.5 rounded-tile bg-warning-faint border border-warning-line text-caption text-warning">
                        <div className="font-semibold mb-1">{t("coding.notice")}</div>
                        {reviewResult.code_smells.map((s, i) => (
                          <div key={i}>• {s}</div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="p-3 rounded-card bg-surface-2 border border-line text-caption text-muted leading-relaxed" data-testid="review-empty">
                    {t("coding.review_empty")}
                  </p>
                )}

                {/* Who set the problem: from the problem, never a fixed name (the week is in the left column's footer) */}
                {problem.trainer_author && (
                  <div className="p-3 rounded-card bg-surface-2 border border-line text-xs space-y-1" data-testid="problem-attribution">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full bg-brand text-white text-caption font-semibold flex items-center justify-center flex-shrink-0">
                        {problem.trainer_author.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <div className="text-caption text-muted">{t("coding.set_by")}</div>
                        <div className="font-semibold text-ink text-caption">{problem.trainer_author}</div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Unlocked Hints Section */}
                {hints.length > 0 && (
                  <div className="space-y-2 pt-1">
                    <div className="text-caption font-semibold text-ink flex items-center gap-1">
                      <HelpCircle className="w-3.5 h-3.5 text-brand" />
                      <span>{fill("coding.unlocked_hints", { n: hints.length, max: (problem.ai_reviewer?.max_hints || 3) })}</span>
                    </div>
                    {hints.map((hint, index) => (
                      <div
                        key={index}
                        className="p-2.5 rounded-tile bg-surface-2 border border-line-strong text-caption text-ink leading-relaxed"
                      >
                        <strong className="text-brand">{fill("coding.hint_n", { n: index + 1 })}</strong> {hint}
                      </div>
                    ))}
                  </div>
                )}

                {hintError && (
                  <div role="alert" data-testid="hint-error" className="p-2 rounded-tile bg-danger-faint border border-danger-line text-caption text-danger">
                    {hintError}
                  </div>
                )}

                {/* Extra Hint Button */}
                {hints.length < (problem.ai_reviewer?.max_hints || 3) ? (
                  <button
                    onClick={handleRequestHint}
                    disabled={isRequestingHint}
                    className="w-full py-2 bg-line-soft hover:bg-line text-brand text-xs font-semibold rounded-tile border border-line-strong transition-all cursor-pointer flex items-center justify-center gap-1.5"
                    data-testid="request-hint-button"
                  >
                    {isRequestingHint && <RefreshCw className="w-3 h-3 animate-spin" />}
                    <span>{t("coding.ask_hint") || "+ Ask for another hint"}</span>
                  </button>
                ) : (
                  <div className="text-center py-1.5 text-caption font-semibold text-success bg-success-soft rounded-tile">
                    ✓ {t("coding.hints_exhausted") || "All hints unlocked"}
                  </div>
                )}

                {/* Policy note */}
                <div className="text-caption text-muted italic leading-tight">
                  {t("coding.hint_policy") || "Hints only, no full solutions. AI help used in this problem"}:{" "}
                  {hints.length} {hints.length === 1 ? (t("coding.hint_singular") || "hint") : (t("coding.hint_plural") || "hints")}
                </div>

                {/* Trainer note: only when the trainer wrote one for this problem */}
                {problem.trainer_notes && (
                  <div className="pt-2 border-t border-line space-y-1.5">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-ink">
                      <MessageSquareQuote className="w-3.5 h-3.5 text-teal" />
                      <span>{t("coding.trainer_note")}</span>
                    </div>
                    <blockquote className="text-caption text-ink-soft italic bg-surface-2 p-2.5 rounded-tile border-l-2 border-teal">
                      &ldquo;{problem.trainer_notes}&rdquo;
                      {problem.trainer_author && (
                        <div className="text-right font-semibold text-caption text-ink not-italic mt-1">– {problem.trainer_author}</div>
                      )}
                    </blockquote>
                  </div>
                )}
              </div>
            </div>

          </div>
        )}

        {/* 20-PROBLEM CURRICULUM NAVIGATOR SLIDE-OVER DRAWER */}
        {isDrawerOpen && (
          <div className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-xs transition-opacity" data-testid="curriculum-drawer">
            <div className="w-full max-w-md bg-white h-full shadow-pop flex flex-col overflow-hidden animate-in slide-in-from-right duration-200">
              {/* Drawer Header */}
              <div className="p-4 border-b border-line flex items-center justify-between bg-surface-2">
                <div>
                  <div className="flex items-center gap-2">
                    <Layers className="w-4 h-4 text-brand" />
                    <h3 className="font-semibold text-sm text-ink">{t("coding.drawer_title")}</h3>
                  </div>
                  <p className="text-caption text-muted mt-0.5">
                    {fill("coding.drawer_solved", { solved: solvedCount, total: allProblems.length })}
                  </p>
                </div>
                <button
                  onClick={() => setIsDrawerOpen(false)}
                  aria-label={t("coding.close")}
                  className="p-1.5 rounded-tile hover:bg-slate-200 text-muted hover:text-ink transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Search & Week Filter Controls */}
              <div className="p-3 border-b border-line space-y-2 bg-white">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-subtle absolute left-3 top-2.5" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder={t("coding.search_placeholder")}
                    aria-label={t("coding.search_placeholder")}
                    className="w-full pl-9 pr-3 py-1.5 bg-surface-2 border border-line rounded-tile text-xs focus:outline-none focus:ring-1 focus:ring-brand"
                  />
                </div>
                {/* Week pills */}
                <div className="flex gap-1 overflow-x-auto pb-1 text-caption">
                  {["All", "1", "2", "3", "4", "5", "6", "7", "8"].map((wk) => (
                    <button
                      key={wk}
                      onClick={() => setSelectedWeekFilter(wk)}
                      className={`px-2.5 py-0.5 rounded-full font-semibold transition-all cursor-pointer whitespace-nowrap ${
                        selectedWeekFilter === wk
                          ? "bg-brand text-white"
                          : "bg-line-soft text-muted hover:bg-line"
                      }`}
                    >
                      {wk === "All" ? t("coding.all_weeks") : t("coding.week_n").replace("{n}", String(wk))}
                    </button>
                  ))}
                </div>
              </div>

              {/* Problems List */}
              <div className="flex-1 overflow-y-auto divide-y divide-line p-2">
                {filteredProblems.map((p, idx) => {
                  const isCurrent = p.id === problemId;
                  return (
                    <Link
                      key={p.id}
                      href={`/student/coding/${p.id}`}
                      onClick={() => setIsDrawerOpen(false)}
                      data-testid={`drawer-problem-${p.id}`}
                      className={`block p-3 rounded-card transition-all cursor-pointer ${
                        isCurrent
                          ? "bg-blue-50/80 border border-brand-line"
                          : "hover:bg-surface-2"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-start gap-2.5 min-w-0">
                          <div className={`w-5 h-5 rounded-full flex items-center justify-center text-caption font-semibold flex-shrink-0 mt-0.5 ${
                            p.is_solved
                              ? "bg-success-soft text-success"
                              : isCurrent
                                ? "bg-brand text-white"
                                : "bg-slate-100 text-muted"
                          }`}>
                            {p.is_solved ? <CheckCircle2 className="w-3.5 h-3.5" /> : (p.curriculum_index || idx + 1)}
                          </div>
                          <div className="min-w-0">
                            <div className="text-xs font-semibold text-ink truncate">
                              {p.title}
                            </div>
                            <div className="text-caption text-muted flex items-center gap-1.5 mt-0.5">
                              {p.week_info && <><span>{p.week_info.split("·")[0].trim()}</span><span>•</span></>}
                              <span className="truncate">{p.topic}</span>
                            </div>
                          </div>
                        </div>

                        <span className={
                          p.difficulty === "Easy"
                            ? "chip-green text-caption flex-shrink-0"
                            : p.difficulty === "Medium"
                              ? "chip-amber text-caption flex-shrink-0"
                              : "chip-red text-caption flex-shrink-0"
                        }>
                          {p.difficulty}
                        </span>
                      </div>
                    </Link>
                  );
                })}
              </div>

            </div>
          </div>
        )}

        {/* COMPLETION CELEBRATION MODAL */}
        {showSuccessModal && nextTarget && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs" data-testid="completion-modal">
            <div className="max-w-md w-full bg-white rounded-card border border-success-line p-6 shadow-pop space-y-4 text-center mx-4 animate-in zoom-in-95 duration-200">
              <div className="w-14 h-14 mx-auto rounded-full bg-success-soft flex items-center justify-center text-success">
                <Trophy className="w-7 h-7" />
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-semibold text-ink">
                  🎉 {t("coding.accepted_title")}
                </h3>
                <p className="text-xs text-muted">
                  {fill("coding.accepted_desc", { n: runResult?.tests_total ?? 0 })}
                </p>
              </div>

              {/* Next Problem Card */}
              <div className="p-3.5 bg-success-faint border border-success-line rounded-card text-left space-y-1.5">
                <div className="text-caption font-semibold text-success">
                  {t("coding.up_next")}
                </div>
                <div className="font-semibold text-xs text-ink">
                  {nextTarget.title}
                </div>
                <div className="text-caption text-muted">
                  {nextTarget.week_info}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2 pt-2">
                <button
                  onClick={() => setShowSuccessModal(false)}
                  className="flex-1 py-2 text-xs font-semibold text-muted hover:text-ink rounded-card border border-line-strong transition-colors cursor-pointer"
                >
                  {t("coding.stay")}
                </button>
                <button
                  onClick={handleGoToNextProblem}
                  data-testid="modal-next-problem-button"
                  className="flex-1 py-2 bg-success hover:bg-success text-white text-xs font-semibold rounded-card shadow-card transition-all cursor-pointer flex items-center justify-center gap-1.5"
                >
                  <span>{t("coding.solve_next")}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        )}

      </AppShell>
    </RoleGuard>
  );
}
