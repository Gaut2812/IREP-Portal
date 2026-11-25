"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/lib/AuthContext";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi } from "@/lib/api";
import {
  Clock, CheckCircle2, Bookmark, ArrowLeft, ArrowRight, Check,
  AlertTriangle, Maximize2, Minimize2, ShieldAlert, RotateCcw,
  CheckCheck, XCircle, Info, Lock, ChevronDown, ChevronUp
} from "lucide-react";

interface QuestionData {
  id: string;
  number: number;
  section: string;
  topic: string;
  text: string;
  options: Record<string, string>;
  selected_option?: string | null;
  is_marked_for_review?: boolean;
}

interface SectionProgress {
  name: string;
  answered: number;
  total: number;
}

interface TestData {
  id: string;
  title: string;
  category: string;
  duration_min: number;
  time_remaining_sec: number;
  total_questions: number;
  attempt_id?: string | null;
  sections: SectionProgress[];
  saved_answers: Record<string, string>;
  marked_for_review: number[];
  questions: QuestionData[];
}

interface QuestionReview {
  number: number;
  section: string;
  topic: string;
  text: string;
  options: Record<string, string>;
  selected_option: string | null;
  correct_option: string;
  is_correct: boolean;
  explanation?: string;
}

interface SectionAnalysis {
  section: string;
  score: string;
  percentage: number;
  status: "Strong" | "Good" | "Needs Support";
}

interface ResultData {
  success: boolean;
  attempt_id: string;
  score: number;
  total: number;
  accuracy: string;
  time_taken: string;
  section_analysis: SectionAnalysis[];
  questions_review: QuestionReview[];
}

export default function PracticeTestPage() {
  const params = useParams();
  const router = useRouter();
  const testId = (params?.id as string) || "test_service_aptitude";

  const { user, logout } = useAuth();
  const { t } = useLanguage();

  // State Management
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testData, setTestData] = useState<TestData | null>(null);
  const [attemptId, setAttemptId] = useState<string | null>(null);

  const [currentQ, setCurrentQ] = useState(12);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [markedForReview, setMarkedForReview] = useState<number[]>([]);
  const [secondsLeft, setSecondsLeft] = useState<number>(1800);
  const [totalDurationSec, setTotalDurationSec] = useState<number>(1800);

  const [isFullscreen, setIsFullscreen] = useState(false);
  const [tabSwitchCount, setTabSwitchCount] = useState(0);
  const [showCopyNotice, setShowCopyNotice] = useState(false);
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [resultData, setResultData] = useState<ResultData | null>(null);
  const [reviewFilter, setReviewFilter] = useState<"all" | "correct" | "incorrect">("all");
  const [expandedExplanations, setExpandedExplanations] = useState<Record<number, boolean>>({});

  const dirtyRef = useRef(false);
  const answersRef = useRef(answers);
  answersRef.current = answers;
  const reviewRef = useRef(markedForReview);
  reviewRef.current = markedForReview;

  // 1. Initial Data Fetch & Attempt Resumption
  const loadTestAndAttempt = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchApi<TestData>(`/student/tests/${testId}`);
      setTestData(data);

      const duration = (data.duration_min || 30) * 60;
      setTotalDurationSec(duration);

      // Start or Resume Attempt
      const attemptRes = await fetchApi<{
        attempt_id: string;
        time_remaining_sec: number;
        saved_answers: Record<string, string>;
        marked_for_review: number[];
      }>(`/student/tests/${testId}/attempts`, {
        method: "POST"
      });

      setAttemptId(attemptRes.attempt_id);
      setSecondsLeft(attemptRes.time_remaining_sec > 0 ? attemptRes.time_remaining_sec : data.time_remaining_sec || duration);

      // Initialize saved answers
      const initialAnswers: Record<number, string> = {};
      const srcAnswers = { ...data.saved_answers, ...attemptRes.saved_answers };
      Object.entries(srcAnswers).forEach(([k, v]) => {
        if (v) initialAnswers[parseInt(k, 10)] = v;
      });
      setAnswers(initialAnswers);

      const combinedReview = Array.from(new Set([
        ...(data.marked_for_review || []),
        ...(attemptRes.marked_for_review || [])
      ]));
      setMarkedForReview(combinedReview);

      // If Question 12 exists, default to 12 as per PDF 4 mockup, else Q1
      const q12 = data.questions.find((q) => q.number === 12);
      setCurrentQ(q12 ? 12 : 1);
    } catch (err: any) {
      console.error("Failed to load test:", err);
      setError(err?.message || t("practice_test.error_loading"));
    } finally {
      setLoading(false);
    }
  }, [testId, t]);

  useEffect(() => {
    if (user?.role === "student") {
      loadTestAndAttempt();
    }
  }, [loadTestAndAttempt, user?.role]);

  // 2. Timer Countdown Engine
  // One interval for the whole attempt (not rebuilt every second). The updater
  // only counts down; submitting is a side effect, so it lives in its own effect.
  const timerRunning = !loading && !isSubmitted && !!attemptId;
  useEffect(() => {
    if (!timerRunning) return;
    const timer = setInterval(() => {
      setSecondsLeft((prev) => (prev <= 1 ? 0 : prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [timerRunning]);

  const autoSubmittedRef = useRef(false);
  useEffect(() => {
    if (timerRunning && secondsLeft === 0 && !autoSubmittedRef.current) {
      autoSubmittedRef.current = true;
      handleAutoSubmit();
    }
  }, [timerRunning, secondsLeft]); // eslint-disable-line react-hooks/exhaustive-deps

  // 3. Background Autosave (Every 10 seconds if dirty)
  const saveAnswersBatch = useCallback(async () => {
    if (!attemptId || !dirtyRef.current || isSubmitted) return;

    try {
      await fetchApi(`/student/tests/attempts/${attemptId}/answers`, {
        method: "PUT",
        body: JSON.stringify({
          answers: answersRef.current,
          marked_for_review: reviewRef.current
        })
      });
      dirtyRef.current = false;
    } catch (err) {
      console.warn("Autosave batch failed:", err);
    }
  }, [attemptId, isSubmitted]);

  useEffect(() => {
    const autosaveInterval = setInterval(() => {
      saveAnswersBatch();
    }, 10000);

    return () => clearInterval(autosaveInterval);
  }, [saveAnswersBatch]);

  // 4. Proctoring Listeners: Tab-switch & Copy/Paste Block
  useEffect(() => {
    if (isSubmitted) return;

    const handleVisibilityChange = () => {
      if (document.hidden) {
        setTabSwitchCount((prev) => {
          const next = prev + 1;
          if (attemptId) {
            fetchApi(`/student/tests/attempts/${attemptId}/proctor-events`, {
              method: "POST",
              body: JSON.stringify({
                event_type: "tab_switch",
                details: `Tab switch event #${next}`
              })
            }).catch(() => {});
          }
          return next;
        });
      }
    };

    const handleCopyCut = (e: ClipboardEvent) => {
      e.preventDefault();
      setShowCopyNotice(true);
      setTimeout(() => setShowCopyNotice(false), 3000);
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    document.addEventListener("copy", handleCopyCut);
    document.addEventListener("cut", handleCopyCut);
    document.addEventListener("paste", handleCopyCut);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      document.removeEventListener("copy", handleCopyCut);
      document.removeEventListener("cut", handleCopyCut);
      document.removeEventListener("paste", handleCopyCut);
    };
  }, [attemptId, isSubmitted]);

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
      setIsFullscreen(true);
    } else {
      document.exitFullscreen().catch(() => {});
      setIsFullscreen(false);
    }
  };

  // 5. User Actions
  const handleSelectOption = (opt: string) => {
    setAnswers((prev) => ({
      ...prev,
      [currentQ]: opt
    }));
    dirtyRef.current = true;
  };

  const toggleReview = () => {
    setMarkedForReview((prev) => {
      const next = prev.includes(currentQ)
        ? prev.filter((q) => q !== currentQ)
        : [...prev, currentQ];
      dirtyRef.current = true;
      return next;
    });
  };

  const handleNext = () => {
    saveAnswersBatch();
    const totalQ = testData?.total_questions || 30;
    if (currentQ < totalQ) {
      setCurrentQ(currentQ + 1);
    }
  };

  const handlePrevious = () => {
    saveAnswersBatch();
    if (currentQ > 1) {
      setCurrentQ(currentQ - 1);
    }
  };

  // 6. Submission Handlers
  const handleAutoSubmit = () => {
    if (isSubmitted || submitting) return;
    performSubmit();
  };

  const performSubmit = async () => {
    if (!attemptId) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await fetchApi<ResultData>(`/student/tests/attempts/${attemptId}/submit`, {
        method: "POST",
        body: JSON.stringify({
          answers: answersRef.current,
          marked_for_review: reviewRef.current
        })
      });
      setResultData(res);
      setIsSubmitted(true);
      setShowSubmitModal(false);
    } catch (err: any) {
      // inline message instead of a blocking alert(); answers stay on screen for a retry
      setSubmitError(err?.detail || err?.message || "Submission failed. Please retry.");
      autoSubmittedRef.current = false;
    } finally {
      setSubmitting(false);
    }
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  // --- ROLE GUARD STATE ---
  if (user && user.role !== "student") {
    return (
      <AppShell pageTitle={t("practice_test.title_default")}>
        <div className="max-w-2xl mx-auto my-12 bg-white rounded-card border border-line p-8 shadow-card text-center space-y-6">
          <div className="w-16 h-16 rounded-full bg-danger-soft text-danger flex items-center justify-center mx-auto">
            <Lock className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-semibold text-ink">
            {t("practice_test.unauthorized_role")}
          </h2>
          <p className="text-sm text-muted">
            {t("practice_test.student_role_required")}
          </p>
          <div className="pt-2">
            <button
              onClick={logout}
              className="px-6 py-2.5 bg-brand hover:bg-brand-hover text-white font-semibold text-xs rounded-card shadow-card transition-all cursor-pointer"
            >
              {t("practice_test.switch_to_student")}
            </button>
          </div>
        </div>
      </AppShell>
    );
  }

  // --- LOADING STATE ---
  if (loading) {
    return (
      <AppShell pageTitle={t("practice_test.title_default")}>
        <div className="max-w-7xl mx-auto space-y-4">
          <div className="flex items-center gap-3 text-xs text-muted pb-2 animate-pulse">
            <Info className="w-4 h-4 text-brand" />
            <span>{t("practice_test.loading_test")}</span>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-8 bg-white rounded-card border border-line p-6 space-y-6 shadow-card animate-pulse">
              <div className="h-4 bg-line-soft rounded w-1/3" />
              <div className="h-16 bg-surface-2 rounded w-full" />
              <div className="space-y-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-12 bg-line-soft rounded-card" />
                ))}
              </div>
            </div>
            <div className="lg:col-span-4 space-y-4">
              <div className="bg-white rounded-card border border-line p-6 h-28 animate-pulse" />
              <div className="bg-white rounded-card border border-line p-6 h-56 animate-pulse" />
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  // --- ERROR STATE ---
  if (error || !testData) {
    return (
      <AppShell pageTitle={t("practice_test.title_default")}>
        <div className="max-w-xl mx-auto my-12 bg-white rounded-card border border-line p-8 shadow-card text-center space-y-4">
          <div className="w-14 h-14 rounded-full bg-danger-soft text-danger flex items-center justify-center mx-auto">
            <AlertTriangle className="w-7 h-7" />
          </div>
          <h2 className="text-lg font-semibold text-ink">{error || t("practice_test.not_found")}</h2>
          <div className="flex justify-center gap-3 pt-2">
            <button
              onClick={loadTestAndAttempt}
              className="flex items-center gap-1.5 px-5 py-2.5 bg-brand text-white text-xs font-semibold rounded-card shadow-card cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>{t("practice_test.retry")}</span>
            </button>
            <button
              onClick={() => router.push("/student")}
              className="px-5 py-2.5 bg-line-soft text-ink text-xs font-semibold rounded-card cursor-pointer"
            >
              {t("practice_test.back_to_dashboard")}
            </button>
          </div>
        </div>
      </AppShell>
    );
  }

  // --- POST-SUBMISSION RESULTS VIEW ---
  if (isSubmitted && resultData) {
    const filteredQuestions = resultData.questions_review.filter((q) => {
      if (reviewFilter === "correct") return q.is_correct;
      if (reviewFilter === "incorrect") return !q.is_correct;
      return true;
    });

    return (
      <AppShell pageTitle={testData.title || t("practice_test.title_default")}>
        <div className="max-w-5xl mx-auto space-y-6 pb-12">
          {/* Header Card */}
          <div className="bg-white rounded-card border border-line p-6 shadow-card text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-success-soft text-success flex items-center justify-center mx-auto text-2xl font-semibold">
              ✓
            </div>
            <div>
              <h2 className="text-xl font-semibold text-ink">{t("practice_test.test_submitted")}</h2>
              <p className="text-xs text-muted pt-1">{testData.title}</p>
            </div>

            {/* Metrics Row */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl mx-auto pt-2">
              <div className="p-4 bg-surface-2 rounded-card border border-line">
                <span className="text-xs font-medium text-muted">{t("practice_test.score")}</span>
                <div className="text-2xl font-semibold text-brand pt-1">
                  {resultData.score} / {resultData.total}
                </div>
              </div>
              <div className="p-4 bg-surface-2 rounded-card border border-line">
                <span className="text-xs font-medium text-muted">{t("practice_test.accuracy")}</span>
                <div className="text-2xl font-semibold text-success pt-1">
                  {resultData.accuracy}
                </div>
              </div>
              <div className="p-4 bg-surface-2 rounded-card border border-line">
                <span className="text-xs font-medium text-muted">{t("practice_test.time_taken")}</span>
                <div className="text-2xl font-semibold text-ink pt-1">
                  {resultData.time_taken}
                </div>
              </div>
            </div>
          </div>

          {/* Section Analysis Breakdown */}
          <div className="bg-white rounded-card border border-line p-6 shadow-card space-y-4">
            <h3 className="text-sm font-semibold text-ink border-b border-line pb-2">
              {t("practice_test.section_analysis")}
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {resultData.section_analysis.map((sec) => {
                let badgeClass = "bg-success-soft text-success";
                if (sec.status === "Needs Support") badgeClass = "bg-danger-soft text-danger";
                else if (sec.status === "Good") badgeClass = "bg-brand-soft text-info";

                return (
                  <div key={sec.section} className="p-4 rounded-card border border-line space-y-2">
                    <div className="flex items-center justify-between text-xs font-semibold text-ink">
                      <span>{sec.section}</span>
                      <span className={`text-caption px-2 py-0.5 rounded-full font-semibold ${badgeClass}`}>
                        {sec.status}
                      </span>
                    </div>
                    <div className="flex items-baseline justify-between">
                      <span className="text-xl font-semibold text-brand">{sec.score}</span>
                      <span className="text-xs text-muted font-semibold">{sec.percentage}%</span>
                    </div>
                    <div className="w-full bg-line-soft h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-brand h-full rounded-full"
                        style={{ width: `${sec.percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Questions Review Section */}
          <div className="bg-white rounded-card border border-line p-6 shadow-card space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-line pb-3">
              <h3 className="text-sm font-semibold text-ink">
                {t("practice_test.review_solutions")} ({resultData.questions_review.length})
              </h3>
              <div className="flex items-center gap-1.5">
                {(["all", "correct", "incorrect"] as const).map((filter) => (
                  <button
                    key={filter}
                    onClick={() => setReviewFilter(filter)}
                    className={`px-3 py-1 rounded-tile text-xs font-semibold transition-all cursor-pointer ${
                      reviewFilter === filter
                        ? "bg-brand text-white shadow-card"
                        : "bg-line-soft text-muted hover:bg-line"
                    }`}
                  >
                    {filter === "all" ? "All (30)" : filter === "correct" ? `Correct (${resultData.score})` : `Incorrect (${30 - resultData.score})`}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              {filteredQuestions.map((q) => {
                const isExpanded = !!expandedExplanations[q.number];
                return (
                  <div
                    key={q.number}
                    className={`p-4 rounded-card border transition-all ${
                      q.is_correct ? "border-success-line bg-success-faint/30" : "border-danger-line bg-danger-faint/30"
                    }`}
                  >
                    <div className="flex items-center justify-between pb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-muted">Q{q.number}</span>
                        <span className="chip-blue text-caption font-semibold">{q.section} · {q.topic}</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-xs font-semibold">
                        {q.is_correct ? (
                          <span className="flex items-center gap-1 text-success">
                            <CheckCheck className="w-4 h-4" /> {t("practice_test.correct")}
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-danger">
                            <XCircle className="w-4 h-4" /> {t("practice_test.incorrect")}
                          </span>
                        )}
                      </div>
                    </div>

                    <p className="text-sm font-medium text-ink pt-1 leading-relaxed">
                      {q.text}
                    </p>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-3 text-xs">
                      {Object.entries(q.options).map(([optKey, optText]) => {
                        const isChosen = q.selected_option === optKey;
                        const isCorrectOpt = q.correct_option === optKey;

                        let style = "border-line bg-white text-ink";
                        if (isCorrectOpt) {
                          style = "border-success-line bg-success-soft text-success font-semibold";
                        } else if (isChosen && !q.is_correct) {
                          style = "border-danger-line bg-danger-soft text-danger font-semibold";
                        }

                        return (
                          <div
                            key={optKey}
                            className={`flex items-center gap-2 p-2.5 rounded-tile border text-xs ${style}`}
                          >
                            <span className="w-5 h-5 rounded-full flex items-center justify-center text-caption font-semibold bg-white/70 shadow-card">
                              {optKey}
                            </span>
                            <span>{optText}</span>
                            {isCorrectOpt && <span className="ml-auto text-caption font-semibold">✓ Key</span>}
                            {isChosen && !isCorrectOpt && <span className="ml-auto text-caption font-semibold">Your choice</span>}
                          </div>
                        );
                      })}
                    </div>

                    {/* Explanation toggle */}
                    {q.explanation && (
                      <div className="pt-3 border-t border-line mt-3">
                        <button
                          onClick={() => setExpandedExplanations((prev) => ({ ...prev, [q.number]: !prev[q.number] }))}
                          className="flex items-center gap-1.5 text-xs font-semibold text-brand hover:text-info cursor-pointer"
                        >
                          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                          <span>{t("practice_test.explanation")}</span>
                        </button>
                        {isExpanded && (
                          <div className="mt-2 p-3 bg-white rounded-tile border border-line text-xs text-ink-soft leading-relaxed">
                            {q.explanation}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Return Button */}
          <div className="text-center pt-2">
            <button
              onClick={() => router.push("/student")}
              className="px-8 py-3 bg-brand hover:bg-brand-hover text-white font-semibold text-xs rounded-card shadow-card cursor-pointer transition-all"
            >
              {t("practice_test.done_and_return")}
            </button>
          </div>
        </div>
      </AppShell>
    );
  }

  // --- ACTIVE EXAMINATION VIEW ---
  const currentQuestionData = testData.questions.find((q) => q.number === currentQ) || testData.questions[0];
  const selectedForCurrent = answers[currentQ] || "";
  const totalQuestions = testData.total_questions || testData.questions.length || 30;
  const answeredCount = Object.keys(answers).length;
  const reviewCount = markedForReview.length;
  const unansweredCount = Math.max(0, totalQuestions - answeredCount);

  // Dynamic section calculation
  const sectionCounts: Record<string, { answered: number; total: number }> = {};
  testData.questions.forEach((q) => {
    const s = q.section || "General";
    if (!sectionCounts[s]) sectionCounts[s] = { answered: 0, total: 0 };
    sectionCounts[s].total += 1;
    if (answers[q.number]) sectionCounts[s].answered += 1;
  });

  return (
    <AppShell pageTitle={testData.title || t("practice_test.title_default")}>
      <div className="space-y-4 max-w-7xl mx-auto" onContextMenu={(e) => e.preventDefault()}>

        {/* Proctoring Banner & Controls */}
        <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 bg-white border border-line rounded-card text-xs shadow-card">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-brand" />
            <span className="font-semibold text-ink">{testData.category}</span>
            {tabSwitchCount > 0 && (
              <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-danger-soft text-danger font-semibold text-caption animate-pulse">
                <AlertTriangle className="w-3 h-3" />
                <span>Tab switches: {tabSwitchCount}</span>
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={toggleFullscreen}
              className="flex items-center gap-1 text-muted hover:text-ink font-semibold cursor-pointer"
            >
              {isFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
              <span>{isFullscreen ? t("practice_test.exit_fullscreen") : t("practice_test.enter_fullscreen")}</span>
            </button>
          </div>
        </div>

        {/* Copy Notice Toast */}
        {showCopyNotice && (
          <div className="p-3 bg-warning-soft border border-warning-fill rounded-card text-xs text-warning font-medium flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{t("practice_test.copy_disabled")}</span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

          {/* MAIN QUESTION CARD (8 cols) */}
          <div className="lg:col-span-8 bg-white rounded-card border border-line shadow-card p-6 flex flex-col justify-between space-y-6 min-h-[460px]">
            <div className="space-y-4">
              {/* Top Bar with topic chip and question counter */}
              <div className="flex items-center justify-between border-b border-line pb-3">
                <span className="chip-blue font-semibold text-xs">
                  {currentQuestionData.section} · {currentQuestionData.topic}
                </span>
                <span className="text-xs font-semibold text-muted">
                  {t("practice_test.question")} {currentQ} {t("practice_test.of")} {totalQuestions}
                </span>
              </div>

              {/* Question Statement */}
              <p className="text-sm font-medium text-ink leading-relaxed pt-2 select-none">
                {currentQuestionData.text}
              </p>

              {/* 4 Options (A to D) */}
              <div className="space-y-3 pt-3">
                {Object.entries(currentQuestionData.options).map(([optKey, optText]) => {
                  const isSelected = selectedForCurrent === optKey;
                  return (
                    <button
                      key={optKey}
                      type="button"
                      onClick={() => handleSelectOption(optKey)}
                      className={`w-full flex items-center gap-3.5 p-3.5 rounded-card border text-left text-xs font-medium transition-all cursor-pointer ${
                        isSelected
                          ? "border-brand bg-brand-soft text-info font-semibold shadow-card ring-1 ring-brand"
                          : "border-line bg-white text-ink hover:bg-surface-2"
                      }`}
                    >
                      <span
                        className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold ${
                          isSelected ? "bg-brand text-white" : "bg-line-soft text-muted"
                        }`}
                      >
                        {optKey}
                      </span>
                      <span className="text-sm select-none">{optText}</span>
                      {isSelected && <Check className="w-4 h-4 ml-auto text-brand" />}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Bottom Actions Bar */}
            <div className="flex items-center justify-between border-t border-line pt-4">
              <button
                onClick={handlePrevious}
                disabled={currentQ === 1}
                className="flex items-center gap-1.5 px-4 py-2 border border-line-strong text-ink text-xs font-semibold rounded-tile hover:bg-line-soft disabled:opacity-40 transition-all cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>{t("practice_test.previous")}</span>
              </button>

              <button
                onClick={toggleReview}
                className={`flex items-center gap-1.5 px-4 py-2 border rounded-tile text-xs font-semibold transition-all cursor-pointer ${
                  markedForReview.includes(currentQ)
                    ? "bg-warning-soft border-warning-fill text-warning"
                    : "border-line-strong text-muted hover:bg-line-soft"
                }`}
              >
                <Bookmark className="w-3.5 h-3.5" />
                <span>
                  {markedForReview.includes(currentQ)
                    ? t("practice_test.marked_for_review")
                    : t("practice_test.mark_for_review")}
                </span>
              </button>

              <button
                onClick={handleNext}
                className="flex items-center gap-1.5 px-5 py-2 bg-brand hover:bg-brand-hover text-white text-xs font-semibold rounded-tile shadow-card transition-all cursor-pointer"
              >
                <span>{currentQ === totalQuestions ? t("practice_test.submit_test") : t("practice_test.save_and_next")}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* RIGHT COLUMN (4 cols) */}
          <div className="lg:col-span-4 space-y-4">

            {/* Time Remaining Card (PDF 4: Large Red 18:42) */}
            <div className="bg-white rounded-card border border-line p-4 shadow-card space-y-2">
              <div className="flex items-center justify-between text-xs text-muted font-medium">
                <span>{t("practice_test.time_remaining")}</span>
                <Clock className="w-3.5 h-3.5 text-danger" />
              </div>
              <div className="text-3xl font-semibold text-danger tracking-tight">
                {formatTime(secondsLeft)}
              </div>
              <div className="w-full bg-danger-soft h-1.5 rounded-full overflow-hidden">
                <div
                  className="bg-danger h-full rounded-full transition-all duration-1000"
                  style={{ width: `${Math.min(100, (secondsLeft / totalDurationSec) * 100)}%` }}
                />
              </div>
            </div>

            {/* Question Palette (6 columns grid) */}
            <div className="bg-white rounded-card border border-line p-4 shadow-card space-y-3">
              <div className="flex items-center justify-between text-xs font-semibold text-ink border-b border-line pb-2">
                <span>{t("practice_test.question_palette")}</span>
                <span className="text-caption text-muted">
                  {totalQuestions} {t("practice_test.question")}s
                </span>
              </div>

              {/* 6-column numbered squares */}
              <div className="grid grid-cols-6 gap-2 pt-1">
                {Array.from({ length: totalQuestions }, (_, i) => i + 1).map((qNum) => {
                  const isCurrent = qNum === currentQ;
                  const isAnswered = !!answers[qNum];
                  const isReview = markedForReview.includes(qNum);

                  let bgClass = "bg-line-soft text-muted border-line";
                  if (isCurrent) {
                    bgClass = "bg-brand text-white border-brand ring-2 ring-brand-line";
                  } else if (isReview) {
                    bgClass = "bg-warning-soft text-warning border-warning-line";
                  } else if (isAnswered) {
                    bgClass = "bg-success-soft text-success border-success-line";
                  }

                  return (
                    <button
                      key={qNum}
                      type="button"
                      onClick={() => {
                        saveAnswersBatch();
                        setCurrentQ(qNum);
                      }}
                      className={`h-8 rounded-tile text-xs font-semibold border flex items-center justify-center transition-all cursor-pointer ${bgClass}`}
                    >
                      {qNum}
                    </button>
                  );
                })}
              </div>

              {/* Palette Legend */}
              <div className="flex items-center justify-between text-caption pt-3 border-t border-line">
                <span className="chip-green">{t("practice_test.legend_answered")} {answeredCount}</span>
                <span className="chip-amber">{t("practice_test.legend_review")} {reviewCount}</span>
                <span className="chip-blue">{t("practice_test.legend_current")}</span>
              </div>
            </div>

            {/* Sections Progress Card */}
            <div className="bg-white rounded-card border border-line p-4 shadow-card space-y-2.5">
              <div className="text-xs font-semibold text-ink border-b border-line pb-2">
                {t("practice_test.sections")}
              </div>
              <div className="space-y-2 text-xs">
                {Object.entries(sectionCounts).map(([secName, counts]) => (
                  <div key={secName} className="flex items-center justify-between">
                    <span className="text-ink font-medium">{secName}</span>
                    <span className="font-semibold text-brand">
                      {counts.answered} / {counts.total}
                    </span>
                  </div>
                ))}
              </div>

              <button
                onClick={() => { setSubmitError(null); setShowSubmitModal(true); }}
                className="w-full mt-3 py-2.5 bg-teal hover:bg-teal-hover text-white font-semibold text-xs rounded-card shadow-card transition-all cursor-pointer"
              >
                {t("practice_test.submit_test")}
              </button>
            </div>

          </div>

        </div>

      </div>

      {/* Submit Test Confirmation Modal */}
      {showSubmitModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-card max-w-sm w-full p-6 space-y-4 shadow-pop border border-line">
            <h3 className="text-base font-semibold text-ink">{t("practice_test.ready_to_submit")}</h3>
            <p className="text-xs text-muted">{t("practice_test.submit_modal_sub")}</p>
            <div className="space-y-1.5 text-xs text-muted p-3 bg-surface-2 rounded-card border border-line">
              <div className="flex justify-between">
                <span>{t("practice_test.legend_answered")}:</span>
                <strong className="text-success">{answeredCount} {t("practice_test.question")}s</strong>
              </div>
              <div className="flex justify-between">
                <span>{t("practice_test.legend_review")}:</span>
                <strong className="text-warning">{reviewCount} {t("practice_test.question")}s</strong>
              </div>
              <div className="flex justify-between">
                <span>{t("practice_test.legend_unanswered")}:</span>
                <strong className="text-danger">{unansweredCount} {t("practice_test.question")}s</strong>
              </div>
            </div>
            {submitError && (
              <div role="alert" data-testid="submit-error" className="p-2.5 bg-red-50 border border-red-200 rounded-tile text-xs text-red-700 font-medium">{submitError}</div>
            )}
            <div className="flex gap-2.5 pt-2">
              <button
                onClick={() => setShowSubmitModal(false)}
                disabled={submitting}
                className="flex-1 py-2 bg-line-soft text-ink font-semibold text-xs rounded-card cursor-pointer"
              >
                {t("practice_test.back_to_test")}
              </button>
              <button
                onClick={performSubmit}
                disabled={submitting}
                className="flex-1 py-2 bg-teal hover:bg-teal-hover text-white font-semibold text-xs rounded-card shadow-card cursor-pointer disabled:opacity-50"
              >
                {submitting ? t("practice_test.submitting") : t("practice_test.confirm_submit")}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
