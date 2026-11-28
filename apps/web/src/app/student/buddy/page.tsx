"use client";

/** Screen 25 · AI Study Buddy: a hint-first tutor with saved chats, an optional course to stay on, a practice-question
 *  mode, and "explain my last failed submission" from the coding lab (?explain=<problemId>). Trainers see only how
 *  often it is used (L21). */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { ConfirmDelete } from "@/components/ui";
import { useLanguage } from "@/lib/LanguageContext";
import { ApiError, fetchApi } from "@/lib/api";
import { Bot, Check, Copy, MessageSquarePlus, Pencil, Send, ShieldCheck, ThumbsDown, ThumbsUp, Trash2, GraduationCap } from "lucide-react";

interface Msg { id: string; role: "user" | "assistant"; content: string; feedback?: "up" | "down" | null }
interface Usage { used_today: number; daily_cap: number; left_today: number }
interface Conversation { id: string; title: string; mode: "tutor" | "practice"; course_id: string | null; course: string | null; updated_at: string | null }
interface Course { id: string; title: string }

/** Answers may hold ```code``` blocks: show them as code with a copy button, the rest as text. */
function MessageBody({ text, t }: { text: string; t: (k: string) => string }) {
  const parts = text.split(/```(\w*)\n?([\s\S]*?)```/g);
  const out: React.ReactNode[] = [];
  for (let i = 0; i < parts.length; i += 3) {
    if (parts[i]) out.push(<span key={`t${i}`} className="whitespace-pre-wrap">{parts[i]}</span>);
    if (i + 2 < parts.length) out.push(<CodeBlock key={`c${i}`} lang={parts[i + 1]} code={parts[i + 2]} t={t} />);
  }
  return <>{out}</>;
}

function CodeBlock({ lang, code, t }: { lang: string; code: string; t: (k: string) => string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* clipboard blocked */ }
  };
  return (
    <div className="my-2 rounded-tile overflow-hidden border border-ink-soft" data-testid="buddy-code">
      <div className="flex items-center justify-between bg-[#141A29] px-2 py-1 text-caption text-line-strong">
        <span className="font-mono">{lang || "code"}</span>
        <button type="button" onClick={copy} className="inline-flex items-center gap-1 hover:text-white" data-testid="buddy-copy">
          {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}{copied ? t("buddy.copied") : t("buddy.copy")}
        </button>
      </div>
      <pre className="bg-[#0F172A] text-line p-2.5 text-caption font-mono overflow-x-auto"><code>{code}</code></pre>
    </div>
  );
}

export default function StudyBuddyPage() {
  const { t } = useLanguage();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [current, setCurrent] = useState<string | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [locked, setLocked] = useState(false);
  const [question, setQuestion] = useState("");
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [newOpen, setNewOpen] = useState(false);
  const [newCourse, setNewCourse] = useState("");
  const [newMode, setNewMode] = useState<"tutor" | "practice">("tutor");
  const [renaming, setRenaming] = useState<{ id: string; title: string } | null>(null);
  const [del, setDel] = useState<Conversation | "all" | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const explained = useRef(false);

  const load = useCallback(async (conversationId: string | null) => {
    try {
      const r = await fetchApi<{ messages: Msg[]; usage: Usage; locked: boolean; conversations: Conversation[]; courses: Course[] }>(
        conversationId ? `/student/buddy?conversation_id=${conversationId}` : "/student/buddy");
      setMsgs(r.messages);
      setUsage(r.usage);
      setLocked(r.locked);
      setConversations(r.conversations);
      setCourses(r.courses);
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : t("buddy.load_failed"));
    }
  }, [t]);

  useEffect(() => { load(current); }, [load, current]);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [msgs, busy]);

  // From the coding lab: "Ask Study Buddy why it failed" opens a new chat about that submission
  useEffect(() => {
    if (explained.current) return;
    const problemId = new URLSearchParams(window.location.search).get("explain");
    if (!problemId) return;
    explained.current = true;
    setBusy(true);
    fetchApi<{ conversation_id: string }>("/student/buddy/explain-submission", { method: "POST", body: JSON.stringify({ problem_id: problemId }) })
      .then((r) => setCurrent(r.conversation_id))
      .catch((e) => setError(e instanceof ApiError ? String(e.detail) : t("buddy.ask_failed")))
      .finally(() => setBusy(false));
  }, [t]);

  const ask = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (q.length < 2) return;
    setBusy(true);
    setError("");
    setMsgs((m) => [...m, { id: `local-${Date.now()}`, role: "user", content: q }]);
    setQuestion("");
    try {
      let conv = current;
      if (!conv) {                                       // the first question starts a chat, named after it
        conv = (await fetchApi<Conversation>("/student/buddy/conversations", { method: "POST", body: JSON.stringify({}) })).id;
      }
      const r = await fetchApi<{ answer: string; answer_id: string; usage: Usage }>("/student/buddy/ask", {
        method: "POST", body: JSON.stringify({ question: q, topic: topic.trim() || null, conversation_id: conv }) });
      setMsgs((m) => [...m, { id: r.answer_id, role: "assistant", content: r.answer }]);
      setUsage(r.usage);
      if (conv !== current) setCurrent(conv); else load(conv);
    } catch (err) {
      // fetchApi already turns {message, message_ta} into the user's language
      setError(err instanceof ApiError && err.detail ? String(err.detail) : t("buddy.ask_failed"));
      await load(current);
    } finally {
      setBusy(false);
    }
  };

  const startChat = async () => {
    setError("");
    try {
      const c = await fetchApi<Conversation>("/student/buddy/conversations", { method: "POST", body: JSON.stringify({ course_id: newCourse || null, mode: newMode }) });
      setNewOpen(false);
      setNewCourse("");
      setNewMode("tutor");
      setCurrent(c.id);
      if (c.mode === "practice") setQuestion(t("buddy.practice_start"));
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("buddy.ask_failed"));
    }
  };

  const rate = async (m: Msg, value: "up" | "down") => {
    const next = m.feedback === value ? null : value;
    setMsgs((all) => all.map((x) => (x.id === m.id ? { ...x, feedback: next } : x)));
    await fetchApi(`/student/buddy/messages/${m.id}/feedback`, { method: "POST", body: JSON.stringify({ value: next }) }).catch(() => undefined);
  };

  const saveRename = async () => {
    if (!renaming || !renaming.title.trim()) return;
    await fetchApi(`/student/buddy/conversations/${renaming.id}`, { method: "PATCH", body: JSON.stringify({ title: renaming.title.trim() }) }).catch(() => undefined);
    setRenaming(null);
    await load(current);
  };

  const active = conversations.find((c) => c.id === current) || null;

  return (
    <RoleGuard allowedRoles={["student"]}>
      <AppShell pageTitle={t("buddy.title")}>
        <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-4 gap-4">
          {/* Chats */}
          <aside className="bg-white rounded-card border border-line p-3 space-y-2 h-fit" data-testid="buddy-conversations">
            <button type="button" onClick={() => setNewOpen((o) => !o)} data-testid="buddy-new"
              className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 bg-brand text-white text-xs font-semibold rounded-tile">
              <MessageSquarePlus className="w-4 h-4" />{t("buddy.new_chat")}
            </button>
            {newOpen && (
              <div className="p-2 rounded-tile border border-line bg-surface-2 space-y-2 text-xs" data-testid="buddy-new-panel">
                <label className="block font-semibold text-ink-soft">{t("buddy.course")}
                  <select value={newCourse} onChange={(e) => setNewCourse(e.target.value)} data-testid="buddy-course"
                    className="mt-1 w-full px-2 py-1.5 border border-line rounded-tile bg-white font-normal">
                    <option value="">{t("buddy.any_topic")}</option>
                    {courses.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
                  </select>
                </label>
                <fieldset className="space-y-1">
                  <legend className="font-semibold text-ink-soft">{t("buddy.mode")}</legend>
                  <label className="flex items-center gap-1.5"><input type="radio" name="mode" checked={newMode === "tutor"} onChange={() => setNewMode("tutor")} />{t("buddy.mode_tutor")}</label>
                  <label className="flex items-center gap-1.5"><input type="radio" name="mode" checked={newMode === "practice"} onChange={() => setNewMode("practice")} data-testid="buddy-mode-practice" />{t("buddy.mode_practice")}</label>
                </fieldset>
                <button type="button" onClick={startChat} data-testid="buddy-start" className="w-full py-1.5 bg-teal text-white font-semibold rounded-tile">{t("buddy.start")}</button>
              </div>
            )}
            <ul className="space-y-1 max-h-[50vh] overflow-y-auto">
              {conversations.map((c) => (
                <li key={c.id} className={`group rounded-tile ${c.id === current ? "bg-brand-soft" : "hover:bg-surface-2"}`} data-testid="buddy-conversation">
                  {renaming?.id === c.id ? (
                    <form onSubmit={(e) => { e.preventDefault(); saveRename(); }} className="p-1.5">
                      <input autoFocus value={renaming.title} onChange={(e) => setRenaming({ id: c.id, title: e.target.value })} onBlur={saveRename} maxLength={120}
                        aria-label={t("buddy.rename")} data-testid="buddy-rename-input" className="w-full px-2 py-1 text-xs border border-brand rounded-tile" />
                    </form>
                  ) : (
                    <div className="flex items-center gap-1 p-1.5">
                      <button type="button" onClick={() => setCurrent(c.id)} aria-current={c.id === current} className="flex-1 min-w-0 text-left">
                        <span className="block text-xs font-medium text-ink truncate">{c.title}</span>
                        <span className="block text-caption text-muted truncate">{c.mode === "practice" ? t("buddy.mode_practice") : t("buddy.mode_tutor")}{c.course ? ` · ${c.course}` : ""}</span>
                      </button>
                      <button type="button" onClick={() => setRenaming({ id: c.id, title: c.title })} aria-label={`${t("buddy.rename")}: ${c.title}`} className="p-1 text-subtle hover:text-brand opacity-0 group-hover:opacity-100 focus:opacity-100"><Pencil className="w-3.5 h-3.5" /></button>
                      <button type="button" onClick={() => setDel(c)} aria-label={`${t("buddy.delete_chat")}: ${c.title}`} data-testid="buddy-delete-chat" className="p-1 text-subtle hover:text-danger opacity-0 group-hover:opacity-100 focus:opacity-100"><Trash2 className="w-3.5 h-3.5" /></button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </aside>

          {/* Chat */}
          <section className="lg:col-span-3 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-ink-soft flex items-center gap-1.5"><ShieldCheck className="w-4 h-4 text-teal" />{t("buddy.privacy")}</p>
              {usage && <span className="text-caption font-semibold text-brand" data-testid="buddy-usage">{usage.left_today}/{usage.daily_cap} {t("buddy.left_today")}</span>}
            </div>
            {active && (active.course || active.mode === "practice") && (
              <p className="text-caption text-ink-soft flex items-center gap-1.5" data-testid="buddy-context">
                <GraduationCap className="w-4 h-4 text-brand" />{active.mode === "practice" ? t("buddy.mode_practice") : t("buddy.mode_tutor")}{active.course ? ` · ${active.course}` : ""}
              </p>
            )}
            {locked && <div className="bg-warning-soft border border-warning-line text-warning text-xs rounded-card p-3" data-testid="buddy-locked">{t("buddy.locked")}</div>}
            <div className="bg-white rounded-card border border-line h-[55vh] overflow-y-auto p-4 space-y-3" data-testid="buddy-chat" aria-live="polite">
              {msgs.length === 0 && (
                <div className="text-center text-xs text-muted pt-16 space-y-2">
                  <Bot className="w-8 h-8 mx-auto text-brand" />
                  <p>{t("buddy.empty")}</p>
                </div>
              )}
              {msgs.map((m) => (
                <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className="max-w-[85%] space-y-1">
                    <div className={`rounded-card px-3 py-2 text-sm ${m.role === "user" ? "bg-brand text-white whitespace-pre-wrap" : "bg-line-soft text-ink"}`}
                      data-testid={m.role === "user" ? "buddy-question" : "buddy-answer"}>
                      {m.role === "assistant" ? <MessageBody text={m.content} t={t} /> : m.content}
                    </div>
                    {m.role === "assistant" && !m.id.startsWith("local") && (
                      <div className="flex gap-1">
                        <button type="button" onClick={() => rate(m, "up")} aria-pressed={m.feedback === "up"} aria-label={t("buddy.helpful")} data-testid="buddy-up"
                          className={`p-1 rounded-tile ${m.feedback === "up" ? "text-success" : "text-subtle hover:text-success"}`}><ThumbsUp className="w-3.5 h-3.5" /></button>
                        <button type="button" onClick={() => rate(m, "down")} aria-pressed={m.feedback === "down"} aria-label={t("buddy.not_helpful")} data-testid="buddy-down"
                          className={`p-1 rounded-tile ${m.feedback === "down" ? "text-danger" : "text-subtle hover:text-danger"}`}><ThumbsDown className="w-3.5 h-3.5" /></button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {busy && <div className="text-xs text-muted" data-testid="buddy-thinking">{t("buddy.thinking")}</div>}
              <div ref={endRef} />
            </div>
            {error && <p className="text-xs text-danger" role="alert" data-testid="buddy-error">{error}</p>}
            <form onSubmit={ask} className="bg-white rounded-card border border-line p-2 space-y-2">
              <input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder={t("buddy.topic_ph")} maxLength={64}
                className="w-full px-2.5 py-1.5 bg-surface-2 border border-line rounded-tile text-xs" aria-label={t("buddy.topic_ph")} data-testid="buddy-topic" />
              <div className="flex gap-2">
                <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={2} maxLength={2000} disabled={locked || busy}
                  placeholder={t("buddy.ask_ph")} aria-label={t("buddy.ask_ph")} data-testid="buddy-input"
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); (e.currentTarget.form as HTMLFormElement).requestSubmit(); } }}
                  className="flex-1 px-2.5 py-1.5 bg-surface-2 border border-line rounded-tile text-sm resize-none" />
                <button type="submit" disabled={locked || busy || question.trim().length < 2} data-testid="buddy-send"
                  className="px-3 bg-brand text-white rounded-tile disabled:opacity-40" aria-label={t("buddy.send")}><Send className="w-4 h-4" /></button>
              </div>
            </form>
            <div className="flex justify-between items-center text-caption text-muted">
              <span>{t("buddy.disclaimer")}</span>
              {conversations.length > 0 && <button type="button" onClick={() => setDel("all")} className="inline-flex items-center gap-1 hover:text-danger" data-testid="buddy-clear"><Trash2 className="w-3.5 h-3.5" />{t("buddy.clear")}</button>}
            </div>
          </section>
        </div>

        {del && (
          <ConfirmDelete itemName={del === "all" ? t("buddy.all_chats") : del.title}
            onConfirm={async () => {
              await fetchApi(del === "all" ? "/student/buddy" : `/student/buddy/conversations/${del.id}`, { method: "DELETE" });
              const closesCurrent = del === "all" || del.id === current;
              if (closesCurrent) setCurrent(null);
              await load(closesCurrent ? null : current);
            }}
            onClose={() => setDel(null)} />
        )}
      </AppShell>
    </RoleGuard>
  );
}
