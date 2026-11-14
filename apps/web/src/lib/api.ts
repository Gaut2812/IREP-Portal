const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("irep_token") : null;
  
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { "Authorization": `Bearer ${token}` } : {}),
    ...((options.headers as Record<string, string>) || {}),
  };

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });
    
    if (!res.ok) {
      throw new Error(`API Error ${res.status}: ${res.statusText}`);
    }
    
    return await res.json();
  } catch (error) {
    console.warn(`Fetch to ${endpoint} failed, falling back or propagating:`, error);
    throw error;
  }
}

// ---------------------------------------------------------------------------
// Screen 11 – My Courses helpers
// ---------------------------------------------------------------------------

export interface CourseCard {
  id: string;
  title: string;
  title_ta: string | null;
  track: string;
  thumbnail_color: string;
  total_lessons: number;
  completed_lessons: number;
  progress_pct: number;
  resume_lesson_id: string | null;
  semester_min: number;
}

export interface LessonItem {
  id: string;
  title: string;
  type: "video" | "slides" | "notes" | "assignment";
  duration_min: number | null;
  content_url: string | null;
  completed: boolean;
}

export interface ModuleItem {
  id: string;
  title: string;
  order_index: number;
  lessons: LessonItem[];
}

export interface CourseDetail {
  course: {
    id: string;
    title: string;
    title_ta: string | null;
    track: string;
    thumbnail_color: string;
    semester_min: number;
  };
  modules: ModuleItem[];
}

export async function getCourses(track?: string): Promise<{ courses: CourseCard[] }> {
  const qs = track ? `?track=${encodeURIComponent(track)}` : "";
  return fetchApi<{ courses: CourseCard[] }>(`/student/courses${qs}`);
}

export async function getCourseDetail(courseId: string): Promise<CourseDetail> {
  return fetchApi<CourseDetail>(`/student/courses/${courseId}`);
}

export async function markLessonProgress(
  courseId: string,
  lessonId: string
): Promise<{ success: boolean; lesson_id: string; completed_at: string }> {
  return fetchApi(`/student/courses/${courseId}/lessons/${lessonId}/progress`, {
    method: "POST",
  });
}

