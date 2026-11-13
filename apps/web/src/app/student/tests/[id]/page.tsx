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

  const { user, switchRoleDemo } = useAuth();
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
  useEffect(() => {
    if (loading || isSubmitted || secondsLeft <= 0) return;

    const timer = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          handleAutoSubmit();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [loading, isSubmitted, secondsLeft]);

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
      console.error("Submission failed:", err);
      alert(err?.message || "Submission failed. Please retry.");
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
        <div className="max-w-2xl mx-auto my-12 bg-white rounded-2xl border border-[#E2E8F0] p-8 shadow-sm text-center space-y-4">
          <div className="w-16 h-16 rounded-full bg-[#FEE2E2] text-[#D93636] flex items-center justify-center mx-auto">
            <Lock className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold text-[#0F1F3A]">
            {t("practice_test.unauthorized_role")}
          </h2>
          <p className="text-sm text-[#64748B]">
            {t("practice_test.student_role_required")}
          </p>
          <div className="pt-2">
            <button
              onClick={() => switchRoleDemo("student")}
              className="px-6 py-2.5 bg-[#2B5CD0] hover:bg-[#1E46B0] text-white font-bold text-xs rounded-xl shadow transition-all cursor-pointer"
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
          <div className="flex items-center gap-3 text-xs text-[#64748B] pb-2 animate-pulse">
            <Info className="w-4 h-4 text-[#2B5CD0]" />
            <span>{t("practice_test.loading_test")}</span>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-8 bg-white rounded-xl border border-[#E2E8F0] p-6 space-y-6 shadow-sm animate-pulse">
              <div className="h-4 bg-[#F1F5F9] rounded w-1/3" />
              <div className="h-16 bg-[#F8FAFC] rounded w-full" />
              <div className="space-y-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-12 bg-[#F1F5F9] rounded-xl" />
                ))}
              </div>
            </div>
            <div className="lg:col-span-4 space-y-4">
              <div className="bg-white rounded-xl border border-[#E2E8F0] p-6 h-28 animate-pulse" />
              <div className="bg-white rounded-xl border border-[#E2E8F0] p-6 h-56 animate-pulse" />
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
        <div className="max-w-xl mx-auto my-12 bg-white rounded-2xl border border-[#E2E8F0] p-8 shadow-sm text-center space-y-4">
          <div className="w-14 h-14 rounded-full bg-[#FEE2E2] text-[#D93636] flex items-center justify-center mx-auto">
            <AlertTriangle className="w-7 h-7" />
          </div>
          <h2 className="text-lg font-bold text-[#0F1F3A]">{error || t("practice_test.not_found")}</h2>
          <div className="flex justify-center gap-3 pt-2">
            <button
              onClick={loadTestAndAttempt}
              className="flex items-center gap-1.5 px-5 py-2.5 bg-[#2B5CD0] text-white text-xs font-bold rounded-xl shadow cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>{t("practice_test.retry")}</span>
            </button>
            <button
              onClick={() => router.push("/student")}
              className="px-5 py-2.5 bg-[#F1F5F9] text-[#0F1F3A] text-xs font-bold rounded-xl cursor-pointer"
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
          <div className="bg-white rounded-2xl border border-[#E2E8F0] p-6 shadow-sm text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-[#DCFCE7] text-[#15803D] flex items-center justify-center mx-auto text-2xl font-black">
              ✓
            </div>
            <div>
              <h2 className="text-xl font-black text-[#0F1F3A]">{t("practice_test.test_submitted")}</h2>
              <p className="text-xs text-[#64748B] pt-1">{testData.title}</p>
            </div>

            {/* Metrics Row */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl mx-auto pt-2">
              <div className="p-4 bg-[#F8FAFC] rounded-xl border border-[#E2E8F0]">
                <span className="text-xs font-medium text-[#64748B]">{t("practice_test.score")}</span>
                <div className="text-2xl font-black text-[#2B5CD0] pt-1">
                  {resultData.score} / {resultData.total}
                </div>
              </div>
              <div className="p-4 bg-[#F8FAFC] rounded-xl border border-[#E2E8F0]">
                <span className="text-xs font-medium text-[#64748B]">{t("practice_test.accuracy")}</span>
                <div className="text-2xl font-black text-[#15803D] pt-1">
                  {resultData.accuracy}
                </div>
              </div>
              <div className="p-4 bg-[#F8FAFC] rounded-xl border border-[#E2E8F0]">
                <span className="text-xs font-medium text-[#64748B]">{t("practice_test.time_taken")}</span>
                <div className="text-2xl font-black text-[#0F1F3A] pt-1">
                  {resultData.time_taken}
                </div>
              </div>
            </div>
          </div>

          {/* Section Analysis Breakdown */}
          <div className="bg-white rounded-2xl border border-[#E2E8F0] p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">
              {t("practice_test.section_analysis")}
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {resultData.section_analysis.map((sec) => {
                let badgeClass = "bg-[#DCFCE7] text-[#15803D]";
                if (sec.status === "Needs Support") badgeClass = "bg-[#FEE2E2] text-[#D93636]";
                else if (sec.status === "Good") badgeClass = "bg-[#EFF6FF] text-[#1D4ED8]";

                return (
                  <div key={sec.section} className="p-4 rounded-xl border border-[#E2E8F0] space-y-2">
                    <div className="flex items-center justify-between text-xs font-bold text-[#0F1F3A]">
                      <span>{sec.section}</span>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${badgeClass}`}>
                        {sec.status}
                      </span>
                    </div>
                    <div className="flex items-baseline justify-between">
                      <span className="text-xl font-black text-[#2B5CD0]">{sec.score}</span>
                      <span className="text-xs text-[#64748B] font-semibold">{sec.percentage}%</span>
                    </div>
                    <div className="w-full bg-[#F1F5F9] h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-[#2B5CD0] h-full rounded-full"
                        style={{ width: `${sec.percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Questions Review Section */}
          <div className="bg-white rounded-2xl border border-[#E2E8F0] p-6 shadow-sm space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E2E8F0] pb-3">
              <h3 className="text-sm font-bold text-[#0F1F3A]">
                {t("practice_test.review_solutions")} ({resultData.questions_review.length})
              </h3>
              <div className="flex items-center gap-1.5">
                {(["all", "correct", "incorrect"] as const).map((filter) => (
                  <button
                    key={filter}
                    onClick={() => setReviewFilter(filter)}
                    className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                      reviewFilter === filter
                        ? "bg-[#2B5CD0] text-white shadow-xs"
                        : "bg-[#F1F5F9] text-[#64748B] hover:bg-[#E2E8F0]"
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
                    className={`p-4 rounded-xl border transition-all ${
                      q.is_correct ? "border-[#BBF7D0] bg-[#F0FDF4]/30" : "border-[#FECACA] bg-[#FEF2F2]/30"
                    }`}
                  >
                    <div className="flex items-center justify-between pb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-[#64748B]">Q{q.number}</span>
                        <span className="chip-blue text-[11px] font-semibold">{q.section} · {q.topic}</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-xs font-bold">
                        {q.is_correct ? (
                          <span className="flex items-center gap-1 text-[#15803D]">
                            <CheckCheck className="w-4 h-4" /> {t("practice_test.correct")}
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-[#D93636]">
                            <XCircle className="w-4 h-4" /> {t("practice_test.incorrect")}
                          </span>
                        )}
                      </div>
                    </div>

                    <p className="text-sm font-medium text-[#0F1F3A] pt-1 leading-relaxed">
                      {q.text}
                    </p>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-3 text-xs">
                      {Object.entries(q.options).map(([optKey, optText]) => {
                        const isChosen = q.selected_option === optKey;
                        const isCorrectOpt = q.correct_option === optKey;

                        let style = "border-[#E2E8F0] bg-white text-[#0F1F3A]";
                        if (isCorrectOpt) {
                          style = "border-[#86EFAC] bg-[#DCFCE7] text-[#15803D] font-bold";
                        } else if (isChosen && !q.is_correct) {
                          style = "border-[#FCA5A5] bg-[#FEE2E2] text-[#B91C1C] font-bold";
                        }

                        return (
                          <div
                            key={optKey}
                            className={`flex items-center gap-2 p-2.5 rounded-lg border text-xs ${style}`}
                          >
                            <span className="w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold bg-white/70 shadow-xs">
                              {optKey}
                            </span>
                            <span>{optText}</span>
                            {isCorrectOpt && <span className="ml-auto text-[10px] uppercase font-bold">✓ Key</span>}
                            {isChosen && !isCorrectOpt && <span className="ml-auto text-[10px] uppercase font-bold">Your choice</span>}
                          </div>
                        );
                      })}
                    </div>

                    {/* Explanation toggle */}
                    {q.explanation && (
                      <div className="pt-3 border-t border-[#E2E8F0] mt-3">
                        <button
                          onClick={() => setExpandedExplanations((prev) => ({ ...prev, [q.number]: !prev[q.number] }))}
                          className="flex items-center gap-1.5 text-xs font-bold text-[#2B5CD0] hover:text-[#1D4ED8] cursor-pointer"
                        >
                          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                          <span>{t("practice_test.explanation")}</span>
                        </button>
                        {isExpanded && (
                          <div className="mt-2 p-3 bg-white rounded-lg border border-[#E2E8F0] text-xs text-[#334155] leading-relaxed">
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
              className="px-8 py-3 bg-[#2B5CD0] hover:bg-[#1E46B0] text-white font-bold text-xs rounded-xl shadow cursor-pointer transition-all"
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
        <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 bg-white border border-[#E2E8F0] rounded-xl text-xs shadow-xs">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-[#2B5CD0]" />
            <span className="font-semibold text-[#0F1F3A]">{testData.category}</span>
            {tabSwitchCount > 0 && (
              <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-[#FEE2E2] text-[#B91C1C] font-bold text-[11px] animate-pulse">
                <AlertTriangle className="w-3 h-3" />
                <span>Tab switches: {tabSwitchCount}</span>
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={toggleFullscreen}
              className="flex items-center gap-1 text-[#64748B] hover:text-[#0F1F3A] font-bold cursor-pointer"
            >
              {isFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
              <span>{isFullscreen ? t("practice_test.exit_fullscreen") : t("practice_test.enter_fullscreen")}</span>
            </button>
          </div>
        </div>

        {/* Copy Notice Toast */}
        {showCopyNotice && (
          <div className="p-3 bg-[#FEF3C7] border border-[#F59E0B] rounded-xl text-xs text-[#B45309] font-medium flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{t("practice_test.copy_disabled")}</span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

          {/* MAIN QUESTION CARD (8 cols) */}
          <div className="lg:col-span-8 bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-6 flex flex-col justify-between space-y-6 min-h-[460px]">
            <div className="space-y-4">
              {/* Top Bar with topic chip and question counter */}
              <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
                <span className="chip-blue font-bold text-xs">
                  {currentQuestionData.section} · {currentQuestionData.topic}
                </span>
                <span className="text-xs font-bold text-[#64748B]">
                  {t("practice_test.question")} {currentQ} {t("practice_test.of")} {totalQuestions}
                </span>
              </div>

              {/* Question Statement */}
              <p className="text-sm font-medium text-[#0F1F3A] leading-relaxed pt-2 select-none">
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
                      className={`w-full flex items-center gap-3.5 p-3.5 rounded-xl border text-left text-xs font-medium transition-all cursor-pointer ${
                        isSelected
                          ? "border-[#2B5CD0] bg-[#EFF6FF] text-[#1D4ED8] font-bold shadow-sm ring-1 ring-[#2B5CD0]"
                          : "border-[#E2E8F0] bg-white text-[#0F1F3A] hover:bg-[#F8FAFC]"
                      }`}
                    >
                      <span
                        className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                          isSelected ? "bg-[#2B5CD0] text-white" : "bg-[#F1F5F9] text-[#64748B]"
                        }`}
                      >
                        {optKey}
                      </span>
                      <span className="text-sm select-none">{optText}</span>
                      {isSelected && <Check className="w-4 h-4 ml-auto text-[#2B5CD0]" />}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Bottom Actions Bar */}
            <div className="flex items-center justify-between border-t border-[#E2E8F0] pt-4">
              <button
                onClick={handlePrevious}
                disabled={currentQ === 1}
                className="flex items-center gap-1.5 px-4 py-2 border border-[#CBD5E1] text-[#0F1F3A] text-xs font-bold rounded-lg hover:bg-[#F1F5F9] disabled:opacity-40 transition-all cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>{t("practice_test.previous")}</span>
              </button>

              <button
                onClick={toggleReview}
                className={`flex items-center gap-1.5 px-4 py-2 border rounded-lg text-xs font-bold transition-all cursor-pointer ${
                  markedForReview.includes(currentQ)
                    ? "bg-[#FEF3C7] border-[#F59E0B] text-[#B45309]"
                    : "border-[#CBD5E1] text-[#64748B] hover:bg-[#F1F5F9]"
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
                className="flex items-center gap-1.5 px-5 py-2 bg-[#2B5CD0] hover:bg-[#1E46B0] text-white text-xs font-bold rounded-lg shadow transition-all cursor-pointer"
              >
                <span>{currentQ === totalQuestions ? t("practice_test.submit_test") : t("practice_test.save_and_next")}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* RIGHT COLUMN (4 cols) */}
          <div className="lg:col-span-4 space-y-4">

            {/* Time Remaining Card (PDF 4: Large Red 18:42) */}
            <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-2">
              <div className="flex items-center justify-between text-xs text-[#64748B] font-medium">
                <span>{t("practice_test.time_remaining")}</span>
                <Clock className="w-3.5 h-3.5 text-[#D93636]" />
              </div>
              <div className="text-3xl font-black text-[#D93636] tracking-tight">
                {formatTime(secondsLeft)}
              </div>
              <div className="w-full bg-[#FEE2E2] h-1.5 rounded-full overflow-hidden">
                <div
                  className="bg-[#D93636] h-full rounded-full transition-all duration-1000"
                  style={{ width: `${Math.min(100, (secondsLeft / totalDurationSec) * 100)}%` }}
                />
              </div>
            </div>

            {/* Question Palette (6 columns grid) */}
            <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-3">
              <div className="flex items-center justify-between text-xs font-bold text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">
                <span>{t("practice_test.question_palette")}</span>
                <span className="text-[11px] text-[#64748B]">
                  {totalQuestions} {t("practice_test.question")}s
                </span>
              </div>

              {/* 6-column numbered squares */}
              <div className="grid grid-cols-6 gap-2 pt-1">
                {Array.from({ length: totalQuestions }, (_, i) => i + 1).map((qNum) => {
                  const isCurrent = qNum === currentQ;
                  const isAnswered = !!answers[qNum];
                  const isReview = markedForReview.includes(qNum);

                  let bgClass = "bg-[#F1F5F9] text-[#64748B] border-[#E2E8F0]";
                  if (isCurrent) {
                    bgClass = "bg-[#2B5CD0] text-white border-[#2B5CD0] ring-2 ring-[#BFDBFE]";
                  } else if (isReview) {
                    bgClass = "bg-[#FEF3C7] text-[#B45309] border-[#FDE68A]";
                  } else if (isAnswered) {
                    bgClass = "bg-[#DCFCE7] text-[#15803D] border-[#BBF7D0]";
                  }

                  return (
                    <button
                      key={qNum}
                      type="button"
                      onClick={() => {
                        saveAnswersBatch();
                        setCurrentQ(qNum);
                      }}
                      className={`h-8 rounded-lg text-xs font-bold border flex items-center justify-center transition-all cursor-pointer ${bgClass}`}
                    >
                      {qNum}
                    </button>
                  );
                })}
              </div>

              {/* Palette Legend */}
              <div className="flex items-center justify-between text-[11px] pt-3 border-t border-[#E2E8F0]">
                <span className="chip-green">{t("practice_test.legend_answered")} {answeredCount}</span>
                <span className="chip-amber">{t("practice_test.legend_review")} {reviewCount}</span>
                <span className="chip-blue">{t("practice_test.legend_current")}</span>
              </div>
            </div>

            {/* Sections Progress Card */}
            <div className="bg-white rounded-xl border border-[#E2E8F0] p-4 shadow-sm space-y-2.5">
              <div className="text-xs font-bold text-[#0F1F3A] border-b border-[#E2E8F0] pb-2">
                {t("practice_test.sections")}
              </div>
              <div className="space-y-2 text-xs">
                {Object.entries(sectionCounts).map(([secName, counts]) => (
                  <div key={secName} className="flex items-center justify-between">
                    <span className="text-[#0F1F3A] font-medium">{secName}</span>
                    <span className="font-bold text-[#2B5CD0]">
                      {counts.answered} / {counts.total}
                    </span>
                  </div>
                ))}
              </div>

              <button
                onClick={() => setShowSubmitModal(true)}
                className="w-full mt-3 py-2.5 bg-[#2BB3A0] hover:bg-[#249B8A] text-white font-bold text-xs rounded-xl shadow transition-all cursor-pointer"
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
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 space-y-4 shadow-2xl border border-[#E2E8F0]">
            <h3 className="text-base font-bold text-[#0F1F3A]">{t("practice_test.ready_to_submit")}</h3>
            <p className="text-xs text-[#64748B]">{t("practice_test.submit_modal_sub")}</p>
            <div className="space-y-1.5 text-xs text-[#64748B] p-3 bg-[#F8FAFC] rounded-xl border border-[#E2E8F0]">
              <div className="flex justify-between">
                <span>{t("practice_test.legend_answered")}:</span>
                <strong className="text-[#15803D]">{answeredCount} {t("practice_test.question")}s</strong>
              </div>
              <div className="flex justify-between">
                <span>{t("practice_test.legend_review")}:</span>
                <strong className="text-[#B45309]">{reviewCount} {t("practice_test.question")}s</strong>
              </div>
              <div className="flex justify-between">
                <span>{t("practice_test.legend_unanswered")}:</span>
                <strong className="text-[#D93636]">{unansweredCount} {t("practice_test.question")}s</strong>
              </div>
            </div>
            <div className="flex gap-2.5 pt-2">
              <button
                onClick={() => setShowSubmitModal(false)}
                disabled={submitting}
                className="flex-1 py-2 bg-[#F1F5F9] text-[#0F1F3A] font-bold text-xs rounded-xl cursor-pointer"
              >
                {t("practice_test.back_to_test")}
              </button>
              <button
                onClick={performSubmit}
                disabled={submitting}
                className="flex-1 py-2 bg-[#2BB3A0] hover:bg-[#249B8A] text-white font-bold text-xs rounded-xl shadow cursor-pointer disabled:opacity-50"
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
