"use client";

/** Screen 25 · AI Study Buddy: a hint-first tutor. Trainers see only how often it is used (L21). */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { Bot, Send, ShieldCheck, Trash2 } from "lucide-react";

interface Msg { id: string; role: "user" | "assistant"; content: string }
interface Usage { used_today: number; daily_cap: number; left_today: number }

export default function StudyBuddyPage() {
  const { t } = useLanguage();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [locked, setLocked] = useState(false);
  const [question, setQuestion] = useState("");
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetchApi<{ messages: Msg[]; usage: Usage; locked: boolean }>("/student/buddy");
      setMsgs(r.messages);
      setUsage(r.usage);
      setLocked(r.locked);
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : t("buddy.load_failed"));
    }
  }, [t]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [msgs, busy]);

  const ask = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (q.length < 2) return;
    setBusy(true);
    setError("");
    setMsgs((m) => [...m, { id: `local-${Date.now()}`, role: "user", content: q }]);
    setQuestion("");
    try {
      const r = await fetchApi<{ answer: string; usage: Usage }>("/student/buddy/ask", { method: "POST", body: JSON.stringify({ question: q, topic: topic.trim() || null }) });
      setMsgs((m) => [...m, { id: `local-a-${Date.now()}`, role: "assistant", content: r.answer }]);
      setUsage(r.usage);
    } catch (err) {
      // fetchApi already turns {message, message_ta} into the user's language
      setError(err instanceof ApiError && err.detail ? String(err.detail) : t("buddy.ask_failed"));
      await load();
    } finally {
      setBusy(false);
    }
  };

  const clear = async () => {
    await fetchApi("/student/buddy", { method: "DELETE" }).catch(() => undefined);
    await load();
  };

  return (
    <RoleGuard allowedRoles={["student"]}>
      <AppShell pageTitle={t("buddy.title")}>
        <div className="max-w-3xl mx-auto space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-[#475569] flex items-center gap-1.5"><ShieldCheck className="w-4 h-4 text-[#2BB3A0]" />{t("buddy.privacy")}</p>
            {usage && <span className="text-[11px] font-bold text-[#2B5CD0]" data-testid="buddy-usage">{usage.left_today}/{usage.daily_cap} {t("buddy.left_today")}</span>}
          </div>
          {locked && <div className="bg-[#FEF3C7] border border-[#FDE68A] text-[#92400E] text-xs rounded-xl p-3" data-testid="buddy-locked">{t("buddy.locked")}</div>}
          <div className="bg-white rounded-xl border border-[#E2E8F0] h-[55vh] overflow-y-auto p-4 space-y-3" data-testid="buddy-chat" aria-live="polite">
            {msgs.length === 0 && (
              <div className="text-center text-xs text-[#64748B] pt-16 space-y-2">
                <Bot className="w-8 h-8 mx-auto text-[#2B5CD0]" />
                <p>{t("buddy.empty")}</p>
              </div>
            )}
            {msgs.map((m) => (
              <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap ${m.role === "user" ? "bg-[#2B5CD0] text-white" : "bg-[#F1F5F9] text-[#0F1F3A]"}`}
                  data-testid={m.role === "user" ? "buddy-question" : "buddy-answer"}>{m.content}</div>
              </div>
            ))}
            {busy && <div className="text-xs text-[#64748B]" data-testid="buddy-thinking">{t("buddy.thinking")}</div>}
            <div ref={endRef} />
          </div>
          {error && <p className="text-xs text-red-600" role="alert" data-testid="buddy-error">{error}</p>}
          <form onSubmit={ask} className="bg-white rounded-xl border border-[#E2E8F0] p-2 space-y-2">
            <input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder={t("buddy.topic_ph")} maxLength={64}
              className="w-full px-2.5 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg text-xs" aria-label={t("buddy.topic_ph")} data-testid="buddy-topic" />
            <div className="flex gap-2">
              <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={2} maxLength={2000} disabled={locked || busy}
                placeholder={t("buddy.ask_ph")} aria-label={t("buddy.ask_ph")} data-testid="buddy-input"
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); (e.currentTarget.form as HTMLFormElement).requestSubmit(); } }}
                className="flex-1 px-2.5 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg text-sm resize-none" />
              <button type="submit" disabled={locked || busy || question.trim().length < 2} data-testid="buddy-send"
                className="px-3 bg-[#2B5CD0] text-white rounded-lg disabled:opacity-40" aria-label={t("buddy.send")}><Send className="w-4 h-4" /></button>
            </div>
          </form>
          <div className="flex justify-between items-center text-[11px] text-[#64748B]">
            <span>{t("buddy.disclaimer")}</span>
            {msgs.length > 0 && <button type="button" onClick={clear} className="inline-flex items-center gap-1 hover:text-red-600" data-testid="buddy-clear"><Trash2 className="w-3.5 h-3.5" />{t("buddy.clear")}</button>}
          </div>
        </div>
      </AppShell>
    </RoleGuard>
  );
}
