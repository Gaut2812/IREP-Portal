"use client";

/** IREP content library: a course's description, thumbnail and intro video, and a lesson's video. Uploads are
 *  scanned by the API; deleting asks first. */
import React, { useState } from "react";
import { Image as ImageIcon, Upload, Video } from "lucide-react";
import { ApiError, fetchApi, mediaSrc } from "@/lib/api";
import { ConfirmDelete, DeleteButton } from "@/components/ui";

export interface MediaCourse {
  id: string; title_en: string; title_ta: string | null; track: string; semester: number; skill_key: string;
  description_en?: string | null; description_ta?: string | null; thumbnail_url?: string | null; intro_video_url?: string | null;
}

function UploadButton({ accept, label, onFile, testId, busy }: { accept: string; label: string; onFile: (f: File) => void; testId: string; busy: boolean }) {
  return (
    <label className={`px-2.5 py-1 border border-line-strong rounded-tile text-caption font-semibold inline-flex items-center gap-1 ${busy ? "opacity-50" : "cursor-pointer hover:bg-surface-2"}`}>
      <Upload className="w-3.5 h-3.5" />{label}
      <input type="file" accept={accept} className="sr-only" disabled={busy} data-testid={testId}
        onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) onFile(f); }} />
    </label>
  );
}

export function CourseMediaPanel({ course, onChange, t }: { course: MediaCourse; onChange: () => Promise<void> | void; t: (k: string) => string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [desc, setDesc] = useState({ en: course.description_en || "", ta: course.description_ta || "" });
  const [del, setDel] = useState<"thumbnail" | "intro_video" | null>(null);

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await fn(); await onChange(); } catch (e) { setError(e instanceof ApiError ? e.detail : t("content.save_failed")); } finally { setBusy(false); }
  };
  const upload = (kind: "thumbnail" | "intro_video", f: File) => run(() => {
    const fd = new FormData();
    fd.append("file", f);
    return fetchApi(`/admin/content/courses/${course.id}/media/${kind}`, { method: "POST", body: fd });
  });
  const saveDesc = () => run(() => fetchApi(`/admin/content/courses/${course.id}`, { method: "PUT", body: JSON.stringify({
    title_en: course.title_en, title_ta: course.title_ta, track: course.track, semester: course.semester, skill_key: course.skill_key,
    description_en: desc.en, description_ta: desc.ta }) }));

  return (
    <div className="bg-white rounded-card border border-line p-3 space-y-3 text-xs" data-testid="course-media">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <label className="font-semibold text-ink-soft">{t("content.description_en")}
          <textarea rows={2} value={desc.en} onChange={(e) => setDesc({ ...desc, en: e.target.value })} data-testid="course-desc-en"
            className="mt-1 w-full px-2.5 py-1.5 bg-surface-2 border border-line rounded-tile font-normal" />
        </label>
        <label className="font-semibold text-ink-soft">{t("content.description_ta")}
          <textarea rows={2} value={desc.ta} onChange={(e) => setDesc({ ...desc, ta: e.target.value })}
            className="mt-1 w-full px-2.5 py-1.5 bg-surface-2 border border-line rounded-tile font-normal" />
        </label>
      </div>
      <button type="button" onClick={saveDesc} disabled={busy} data-testid="course-desc-save" className="px-3 py-1.5 bg-brand text-white font-semibold rounded-tile disabled:opacity-50">{t("content.save_description")}</button>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 border-t border-line-soft">
        <div className="space-y-2">
          <div className="font-semibold text-ink flex items-center gap-1"><ImageIcon className="w-4 h-4 text-brand" />{t("content.thumbnail")}</div>
          {course.thumbnail_url
            ? <img src={mediaSrc(course.thumbnail_url)} alt="" className="w-full aspect-video object-cover rounded-tile border border-line" data-testid="thumb-preview" />
            : <p className="text-caption text-muted">{t("content.no_thumbnail")}</p>}
          <div className="flex gap-2">
            <UploadButton accept="image/png,image/jpeg,image/webp" label={course.thumbnail_url ? t("content.replace") : t("content.upload")} busy={busy} testId="thumb-input" onFile={(f) => upload("thumbnail", f)} />
            {course.thumbnail_url && <DeleteButton onClick={() => setDel("thumbnail")} testId="thumb-delete" />}
          </div>
          <p className="text-caption text-muted">{t("content.thumbnail_hint")}</p>
        </div>
        <div className="space-y-2">
          <div className="font-semibold text-ink flex items-center gap-1"><Video className="w-4 h-4 text-brand" />{t("content.intro_video")}</div>
          {course.intro_video_url
            ? <video controls preload="metadata" src={mediaSrc(course.intro_video_url)} className="w-full rounded-tile bg-ink" data-testid="intro-preview" />
            : <p className="text-caption text-muted">{t("content.no_video")}</p>}
          <div className="flex gap-2">
            <UploadButton accept="video/mp4,video/webm" label={course.intro_video_url ? t("content.replace") : t("content.upload")} busy={busy} testId="intro-input" onFile={(f) => upload("intro_video", f)} />
            {course.intro_video_url && <DeleteButton onClick={() => setDel("intro_video")} testId="intro-delete" />}
          </div>
          <p className="text-caption text-muted">{t("content.video_hint")}</p>
        </div>
      </div>
      {busy && <p className="text-caption text-muted" role="status">{t("content.uploading")}</p>}
      {error && <p className="text-caption text-danger" role="alert" data-testid="media-error">{error}</p>}
      {del && (
        <ConfirmDelete itemName={del === "thumbnail" ? t("content.thumbnail") : t("content.intro_video")}
          onConfirm={async () => { await fetchApi(`/admin/content/courses/${course.id}/media/${del}`, { method: "DELETE" }); await onChange(); }}
          onClose={() => setDel(null)} />
      )}
    </div>
  );
}

export function LessonVideo({ lessonId, hasVideo, onChange, t }: { lessonId: string; hasVideo: boolean; onChange: () => Promise<void> | void; t: (k: string) => string }) {
  const [busy, setBusy] = useState(false);
  const [del, setDel] = useState(false);
  const upload = async (f: File) => {
    setBusy(true);
    const fd = new FormData();
    fd.append("file", f);
    try { await fetchApi(`/admin/content/lessons/${lessonId}/video`, { method: "POST", body: fd }); await onChange(); } catch { /* the panel shows nothing; retry */ } finally { setBusy(false); }
  };
  return (
    <div className="flex items-center gap-2">
      {hasVideo && <span className="chip-purple text-caption inline-flex items-center gap-1"><Video className="w-3 h-3" />{t("content.has_video")}</span>}
      <UploadButton accept="video/mp4,video/webm" label={hasVideo ? t("content.replace") : t("content.video")} busy={busy} testId={`lesson-video-input-${lessonId}`} onFile={upload} />
      {hasVideo && <DeleteButton onClick={() => setDel(true)} label={t("content.remove_video")} testId={`lesson-video-delete-${lessonId}`} />}
      {del && <ConfirmDelete itemName={t("content.lesson_video")} onConfirm={async () => { await fetchApi(`/admin/content/lessons/${lessonId}/video`, { method: "DELETE" }); await onChange(); }} onClose={() => setDel(false)} />}
    </div>
  );
}
