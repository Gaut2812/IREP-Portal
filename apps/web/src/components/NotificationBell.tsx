"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, CheckCheck, Inbox } from "lucide-react";
import { fetchApi } from "@/lib/api";
import { useLanguage } from "@/lib/LanguageContext";
import { useAuth } from "@/lib/AuthContext";

interface NotificationItem {
  id: string;
  kind: string;
  title: string;
  body?: string | null;
  link?: string | null;
  created_at?: string | null;
  read: boolean;
}

/** Bell icon in the top bar: unread count badge plus a dropdown of recent notifications (Screen 44 lite). */
export const NotificationBell: React.FC = () => {
  const { t, language } = useLanguage();
  const { user, token } = useAuth();
  const pathname = usePathname();
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  const refreshCount = useCallback(async () => {
    try {
      const res = await fetchApi<{ unread: number }>("/notifications/unread-count");
      setUnread(res.unread);
    } catch {
      /* offline: keep the last known count */
    }
  }, []);

  useEffect(() => {
    refreshCount();
  }, [refreshCount, pathname, user?.id, token]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const openPanel = async () => {
    const next = !open;
    setOpen(next);
    if (!next) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchApi<{ items: NotificationItem[]; unread: number }>(`/notifications?lang=${language}&limit=12`);
      setItems(res.items);
      setUnread(res.unread);
    } catch {
      setError(t("notifications.load_error"));
    } finally {
      setLoading(false);
    }
  };

  const markAll = async () => {
    try {
      await fetchApi("/notifications/read-all", { method: "POST" });
      setItems((prev) => prev.map((i) => ({ ...i, read: true })));
      setUnread(0);
    } catch {
      setError(t("notifications.load_error"));
    }
  };

  const markOne = async (item: NotificationItem) => {
    if (item.read) return;
    try {
      await fetchApi(`/notifications/${item.id}/read`, { method: "POST" });
      setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, read: true } : i)));
      setUnread((u) => Math.max(0, u - 1));
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={openPanel}
        aria-label={t("notifications.title")}
        data-testid="notification-bell"
        className="relative cursor-pointer p-1.5 hover:bg-[#F1F5F9] rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2B5CD0]"
      >
        <Bell className="w-4 h-4 text-[#64748B]" />
        {unread > 0 && (
          <span
            data-testid="notification-unread"
            className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-[#D93636] text-white text-[9px] font-bold flex items-center justify-center"
          >
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-1.5 w-80 bg-white rounded-xl shadow-xl border border-[#E2E8F0] z-50 text-xs overflow-hidden">
          <div className="flex items-center justify-between px-3 py-2 border-b border-[#E2E8F0]">
            <span className="font-bold text-[#0F1F3A]">{t("notifications.title")}</span>
            <button type="button" onClick={markAll} className="flex items-center gap-1 text-[11px] font-semibold text-[#2B5CD0] hover:underline">
              <CheckCheck className="w-3.5 h-3.5" /> {t("notifications.mark_all_read")}
            </button>
          </div>
          <div className="max-h-80 overflow-y-auto">
            {loading && (
              <div className="p-3 space-y-2 animate-pulse">
                {[1, 2, 3].map((i) => <div key={i} className="h-9 bg-[#F1F5F9] rounded-lg" />)}
              </div>
            )}
            {!loading && error && (
              <div className="p-3 text-[#D93636]">{error}</div>
            )}
            {!loading && !error && items.length === 0 && (
              <div className="p-5 text-center text-[#64748B] flex flex-col items-center gap-1.5">
                <Inbox className="w-5 h-5 text-[#94A3B8]" />
                <span>{t("notifications.empty")}</span>
              </div>
            )}
            {!loading && !error && items.map((item) => {
              const content = (
                <div className={`px-3 py-2.5 border-b border-[#F1F5F9] ${item.read ? "bg-white" : "bg-[#EFF6FF]"} hover:bg-[#F8FAFC]`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="font-semibold text-[#0F1F3A] leading-snug">{item.title}</div>
                    {!item.read && <span className="w-2 h-2 rounded-full bg-[#2B5CD0] mt-1 flex-shrink-0" />}
                  </div>
                  {item.body && <div className="text-[11px] text-[#64748B] mt-0.5 leading-snug">{item.body}</div>}
                </div>
              );
              return item.link ? (
                <Link key={item.id} href={item.link} onClick={() => { markOne(item); setOpen(false); }} className="block">
                  {content}
                </Link>
              ) : (
                <button key={item.id} type="button" onClick={() => markOne(item)} className="block w-full text-left">
                  {content}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
