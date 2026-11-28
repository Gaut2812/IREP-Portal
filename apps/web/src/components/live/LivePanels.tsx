"use client";

/** Live classroom (screen 07) side panels: in-class chat with pinned messages, the raised-hand queue (trainer),
 *  everyone in class with Spotlight (trainer), and the floating reactions. */
import React, { useEffect, useRef, useState } from "react";
import { Hand, Pin, Send, Star, StarOff, Users } from "lucide-react";
import { fetchApi } from "@/lib/api";

export interface ChatMsg { id: string; author: string; role: string; text: string; pinned: boolean; mine: boolean; at: string }
export interface Controls {
  chat: ChatMsg[]; pinned: { id: string; author: string; text: string }[];
  hands: { user_id: string; name: string; raised_at: string }[]; my_hand: boolean;
  reactions: { emoji: string; count: number }[]; reaction_choices: string[];
  spotlight: { user_id: string; name: string } | null;
  all_participants: { user_id: string; name: string; role: string; is_you: boolean }[]; participant_count: number;
}

export function LivePanels({ sessionId, c, isTrainer, t, onChange, onToast }: {
  sessionId: string; c: Controls; isTrainer: boolean; t: (k: string) => string; onChange: () => void; onToast: (s: string) => void;
}) {
  const [text, setText] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [c.chat.length]);

  const call = async (path: string, body?: unknown) => {
    try { await fetchApi(`/live/${sessionId}${path}`, { method: "POST", ...(body !== undefined ? { body: JSON.stringify(body) } : {}) }); onChange(); }
    catch (e: any) { onToast(e?.detail || t("live_class.action_failed")); }
  };
  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    await call("/chat", { text: text.trim() });
    setText("");
  };

  return (
    <>
      {isTrainer && c.hands.length > 0 && (
        <section className="bg-[#1E293B] border border-warning-fill rounded-card p-3.5 space-y-2" data-testid="hands-queue">
          <div className="text-xs font-semibold text-warning-fill flex items-center gap-1.5"><Hand className="w-3.5 h-3.5" />{t("live_class.hands_up").replace("{n}", String(c.hands.length))}</div>
          <ol className="space-y-1">
            {c.hands.map((h, i) => (
              <li key={h.user_id} className="flex items-center justify-between text-caption text-line">
                <span>{i + 1}. {h.name}</span>
                <button type="button" onClick={() => call(`/hands/${h.user_id}/lower`)} className="text-subtle hover:text-white underline" data-testid={`lower-${h.user_id}`}>{t("live_class.lower_hand")}</button>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className="bg-[#1E293B] border border-ink-soft rounded-card p-3.5 space-y-2 flex flex-col min-h-[220px]" id="chat" data-testid="live-chat">
        <div className="text-xs font-semibold text-line">{t("live_class.chat_title")}</div>
        {c.pinned.map((p) => (
          <div key={p.id} className="text-caption bg-[#0F172A] border border-brand rounded-tile p-2 flex gap-1.5" data-testid="chat-pinned">
            <Pin className="w-3 h-3 text-brand shrink-0 mt-0.5" /><span><b className="text-line">{p.author}:</b> <span className="text-line-strong">{p.text}</span></span>
          </div>
        ))}
        <div className="flex-1 overflow-y-auto space-y-1.5 max-h-56" aria-live="polite">
          {c.chat.length === 0 && <p className="text-caption text-subtle">{t("live_class.chat_empty")}</p>}
          {c.chat.map((m) => (
            <div key={m.id} className="group text-caption" data-testid="chat-msg">
              <span className={`font-semibold ${m.role === "trainer" ? "text-teal" : "text-line"}`}>{m.mine ? t("live_class.you") : m.author}: </span>
              <span className="text-line-strong break-words">{m.text}</span>
              {isTrainer && (
                <button type="button" onClick={() => call(`/chat/${m.id}/pin`)} aria-label={m.pinned ? t("live_class.unpin") : t("live_class.pin")}
                  className="ml-1 text-subtle hover:text-white opacity-0 group-hover:opacity-100 focus:opacity-100" data-testid={`pin-${m.id}`}><Pin className="w-3 h-3 inline" /></button>
              )}
            </div>
          ))}
          <div ref={endRef} />
        </div>
        <form onSubmit={send} className="flex gap-1.5">
          <input value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} placeholder={t("live_class.chat_ph")} aria-label={t("live_class.chat_ph")} data-testid="chat-input"
            className="flex-1 px-2.5 py-1.5 bg-[#0F172A] border border-ink-soft rounded-tile text-xs text-white placeholder-muted focus:outline-none focus:border-brand" />
          <button type="submit" aria-label={t("live_class.send")} className="px-2.5 bg-brand rounded-tile" data-testid="chat-send"><Send className="w-3.5 h-3.5" /></button>
        </form>
      </section>

      {isTrainer && (
        <section className="bg-[#1E293B] border border-ink-soft rounded-card p-3.5 space-y-2" data-testid="people">
          <div className="text-xs font-semibold text-line flex items-center gap-1.5"><Users className="w-3.5 h-3.5" />{t("live_class.in_class").replace("{n}", String(c.participant_count))}</div>
          <ul className="space-y-1 max-h-40 overflow-y-auto">
            {c.all_participants.filter((p) => !p.is_you).map((p) => {
              const on = c.spotlight?.user_id === p.user_id;
              return (
                <li key={p.user_id} className="flex items-center justify-between text-caption text-line">
                  <span>{p.name}{c.hands.some((h) => h.user_id === p.user_id) ? " ✋" : ""}</span>
                  <button type="button" onClick={() => call("/spotlight", { user_id: on ? null : p.user_id })} className={`inline-flex items-center gap-0.5 ${on ? "text-warning-fill" : "text-subtle hover:text-white"}`} data-testid={`spotlight-${p.user_id}`}>
                    {on ? <StarOff className="w-3 h-3" /> : <Star className="w-3 h-3" />}{on ? t("live_class.unspotlight") : t("live_class.spotlight")}
                  </button>
                </li>
              );
            })}
            {c.all_participants.filter((p) => !p.is_you).length === 0 && <li className="text-caption text-subtle">{t("live_class.nobody_yet")}</li>}
          </ul>
        </section>
      )}
    </>
  );
}

/** Reactions floating over the stage for a few seconds. */
export function ReactionBubbles({ reactions }: { reactions: { emoji: string; count: number }[] }) {
  if (!reactions.length) return null;
  return (
    <div className="absolute right-4 bottom-4 flex flex-col items-end gap-1 pointer-events-none" data-testid="reaction-bubbles" aria-hidden="true">
      {reactions.map((r) => (
        <span key={r.emoji} className="px-2 py-1 rounded-full bg-[#0F172A]/80 border border-ink-soft text-base animate-bounce">{r.emoji}{r.count > 1 ? ` ${r.count}` : ""}</span>
      ))}
    </div>
  );
}
