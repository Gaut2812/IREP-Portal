"use client";

import React, { useEffect, useState, useMemo } from "react";
import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/RoleGuard";
import { Button } from "@/components/ui";
import { useLanguage } from "@/lib/LanguageContext";
import { fetchApi } from "@/lib/api";
import {
  Briefcase, Plus, ExternalLink, CheckCircle2,
  Award, Star, Trash2, Edit3, X, RefreshCw, AlertCircle,
  FileText, Sparkles, Layers, Cpu, ShieldCheck, UserCheck,
  FolderGit2
} from "lucide-react";

interface Project {
  id: string;
  title: string;
  tagline?: string;
  category: string;
  description: string;
  parent_summary?: string;
  role_description?: string;
  team_size: number;
  team_name: string;
  tech_stack: string[];
  github_url: string;
  live_demo_url?: string;
  status: string;
  is_featured: boolean;
  trainer_verified: boolean;
  trainer_name: string;
  trainer_feedback?: string;
  score_percent: number;
}

interface Skill {
  id: string;
  skill_name: string;
  category: string;
  level: string;
  problems_solved: number;
  verified_by: string;
}

interface Certification {
  title: string;
  issuer: string;
  status: string;
  score: string;
}

interface PortfolioData {
  student: {
    id: string;
    name: string;
    roll_no: string;
    branch: string;
    semester: number;
    college: string;
    readiness_score: number;
    readiness_band: string;
    github_url: string;
    linkedin_url: string;
    resume_url: string;
  };
  stats: {
    total_projects: number;
    featured_projects: number;
    verified_skills_count: number;
    problems_solved: number;
    github_commits: number;
    avg_project_score: number;
  };
  projects: Project[];
  verified_skills: Skill[];
  certifications: Certification[];
}

export default function StudentPortfolioPage() {
  const { t, language } = useLanguage();
  const [data, setData] = useState<PortfolioData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<string>("all");

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Form fields
  const [formTitle, setFormTitle] = useState("");
  const [formTagline, setFormTagline] = useState("");
  const [formCategory, setFormCategory] = useState("machine_learning");
  const [formDescription, setFormDescription] = useState("");
  const [formRole, setFormRole] = useState("");
  const [formTeamSize, setFormTeamSize] = useState(1);
  const [formTeamName, setFormTeamName] = useState("Solo Capstone");
  const [formTechStack, setFormTechStack] = useState("");
  const [formGithubUrl, setFormGithubUrl] = useState("");
  const [formLiveDemoUrl, setFormLiveDemoUrl] = useState("");
  const [formIsFeatured, setFormIsFeatured] = useState(false);

  const loadPortfolio = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchApi<PortfolioData>(`/student/portfolio?lang=${language}`);
      setData(res);
    } catch (err: any) {
      console.warn("Failed to fetch student portfolio from API:", err);
      // Fallback offline mock data if backend not reachable
      setData({
        student: {
          id: "std_priya_01",
          name: "Priya R",
          roll_no: "2023-AIDS-042",
          branch: "AI & DS",
          semester: 5,
          college: "Demo Engineering College",
          readiness_score: 74,
          readiness_band: "Nearly Ready",
          github_url: "https://github.com/priya-r",
          linkedin_url: "https://linkedin.com/in/priya-r-demo",
          resume_url: "/downloads/Priya_R_Resume_IREP.pdf"
        },
        stats: {
          total_projects: 4,
          featured_projects: 2,
          verified_skills_count: 6,
          problems_solved: 286,
          github_commits: 48,
          avg_project_score: 92
        },
        projects: [
          {
            id: "proj_crop_01",
            title: "Crop Price Predictor",
            tagline: "Machine learning system for forecasting agricultural market prices using climate & mandi trade data",
            category: "machine_learning",
            description: "Built an end-to-end predictive analytics web platform that estimates wholesale crop prices across Tamil Nadu mandis with 92% accuracy.",
            parent_summary: "Priya led the machine learning forecasting model for this farming tool, helping farmers predict market prices.",
            role_description: "Led ML pipeline development and FastAPI prediction endpoints.",
            team_size: 3,
            team_name: "Team AgriVision",
            tech_stack: ["Python", "Scikit-Learn", "FastAPI", "Pandas", "Streamlit", "PostgreSQL"],
            github_url: "https://github.com/priya-r/crop-price-predictor",
            live_demo_url: "https://crop-price-demo.demo.edu",
            status: "deployed",
            is_featured: true,
            trainer_verified: true,
            trainer_name: "Arun Kumar",
            trainer_feedback: "Exceptional model validation and clear modular structure.",
            score_percent: 94
          },
          {
            id: "proj_clinic_02",
            title: "Clinic Appointment & Token System",
            tagline: "Real-time multi-tenant patient scheduling and digital queue management portal",
            category: "fullstack",
            description: "Full-stack healthcare coordination system supporting doctor schedules and digital queue monitors.",
            parent_summary: "Priya developed the secure patient appointment engine and doctor availability schedule.",
            role_description: "Architected the backend REST APIs and Next.js patient booking UI.",
            team_size: 4,
            team_name: "Team Phoenix",
            tech_stack: ["React", "Next.js", "FastAPI", "PostgreSQL", "Tailwind CSS", "Docker"],
            github_url: "https://github.com/priya-r/clinic-appointment-portal",
            live_demo_url: "https://clinic-demo.demo.edu",
            status: "in_progress",
            is_featured: true,
            trainer_verified: true,
            trainer_name: "Arun Kumar",
            trainer_feedback: "Clean separation of concerns between appointment scheduling and notification queues.",
            score_percent: 88
          }
        ],
        verified_skills: [
          { id: "s1", skill_name: "Data Structures & Algorithms", category: "Core CS", level: "Gold", problems_solved: 286, verified_by: "Arun Kumar" },
          { id: "s2", skill_name: "Machine Learning & Scikit-Learn", category: "Core CS", level: "Advanced", problems_solved: 42, verified_by: "Arun Kumar" },
          { id: "s3", skill_name: "Python Backend & FastAPI", category: "Framework", level: "Proficient", problems_solved: 38, verified_by: "Arun Kumar" },
          { id: "s4", skill_name: "React & Modern Frontend", category: "Framework", level: "Proficient", problems_solved: 30, verified_by: "Arun Kumar" }
        ],
        certifications: [
          { title: "AWS Certified Cloud Practitioner", issuer: "Amazon Web Services", status: "Scheduled for Nov 22", score: "In Progress" },
          { title: "IREP DSA Mastery Level 2", issuer: "Industry-Ready Engineer Program", status: "Verified", score: "94%" }
        ]
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPortfolio();
  }, [language]);

  const openCreateModal = () => {
    setEditingProject(null);
    setFormTitle("");
    setFormTagline("");
    setFormCategory("machine_learning");
    setFormDescription("");
    setFormRole("");
    setFormTeamSize(1);
    setFormTeamName("Solo Capstone");
    setFormTechStack("");
    setFormGithubUrl("");
    setFormLiveDemoUrl("");
    setFormIsFeatured(false);
    setFormError(null);
    setIsModalOpen(true);
  };

  const openEditModal = (p: Project) => {
    setEditingProject(p);
    setFormTitle(p.title);
    setFormTagline(p.tagline || "");
    setFormCategory(p.category);
    setFormDescription(p.description);
    setFormRole(p.role_description || "");
    setFormTeamSize(p.team_size || 1);
    setFormTeamName(p.team_name || "Solo Capstone");
    setFormTechStack(p.tech_stack ? p.tech_stack.join(", ") : "");
    setFormGithubUrl(p.github_url);
    setFormLiveDemoUrl(p.live_demo_url || "");
    setFormIsFeatured(p.is_featured);
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleSaveProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formTitle.trim() || !formDescription.trim() || !formGithubUrl.trim()) {
      setFormError("Please fill in project title, description, and GitHub repository URL.");
      return;
    }

    setIsSubmitting(true);
    setFormError(null);

    const stackList = formTechStack
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s.length > 0);

    const payload = {
      title: formTitle.trim(),
      tagline: formTagline.trim() || formTitle.trim(),
      category: formCategory,
      description: formDescription.trim(),
      role_description: formRole.trim(),
      team_size: Number(formTeamSize) || 1,
      team_name: formTeamName.trim() || "Solo Capstone",
      tech_stack: stackList,
      github_url: formGithubUrl.trim(),
      live_demo_url: formLiveDemoUrl.trim() || null,
      is_featured: formIsFeatured,
      status: "deployed"
    };

    try {
      if (editingProject) {
        await fetchApi(`/student/portfolio/projects/${editingProject.id}`, {
          method: "PUT",
          body: JSON.stringify(payload)
        });
      } else {
        await fetchApi("/student/portfolio/projects", {
          method: "POST",
          body: JSON.stringify(payload)
        });
      }
      setIsModalOpen(false);
      await loadPortfolio();
    } catch (err: any) {
      console.error("Save error:", err);
      setFormError(err.message || "Failed to save project. Please check fields and retry.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteProject = async (projectId: string) => {
    if (!confirm(language === "ta" ? "இந்த திட்டப்பணியை நிச்சயமாக நீக்க வேண்டுமா?" : "Are you sure you want to delete this project?")) {
      return;
    }
    try {
      await fetchApi(`/student/portfolio/projects/${projectId}`, {
        method: "DELETE"
      });
      await loadPortfolio();
    } catch (err: any) {
      alert("Failed to delete project: " + err.message);
    }
  };

  const filteredProjects = useMemo(() => {
    if (!data?.projects) return [];
    if (activeFilter === "all") return data.projects;
    if (activeFilter === "featured") return data.projects.filter((p) => p.is_featured);
    return data.projects.filter((p) => p.category === activeFilter);
  }, [data?.projects, activeFilter]);

  return (
    <RoleGuard allowedRoles={["student"]}>
      <AppShell pageTitle={t("portfolio.title")} pageSubtitle={t("portfolio.subtitle")}
        pageActions={<Button onClick={openCreateModal}><Plus className="w-4 h-4" /><span>{t("portfolio.add_project")}</span></Button>}>
        <div className="max-w-7xl space-y-6 pb-16">

          {/* Loading Skeleton */}
          {loading && !data && (
            <div className="space-y-6">
              <div className="h-44 bg-white rounded-card border border-line p-6 animate-pulse" />
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-24 bg-white rounded-card border border-line animate-pulse" />
                ))}
              </div>
              <div className="h-96 bg-white rounded-card border border-line animate-pulse" />
            </div>
          )}

          {/* Error State */}
          {error && (
            <div className="bg-danger-faint border border-danger-line rounded-card p-6 text-center space-y-3">
              <AlertCircle className="w-8 h-8 text-danger mx-auto" />
              <h3 className="text-base font-semibold text-danger">{t("portfolio.error_loading")}</h3>
              <p className="text-xs text-danger">{error}</p>
              <button
                onClick={loadPortfolio}
                className="px-4 py-2 bg-danger text-white text-xs font-semibold rounded-card hover:bg-danger transition cursor-pointer"
              >
                {t("portfolio.retry")}
              </button>
            </div>
          )}

          {data && (
            <>
              {/* Hero Student Profile Card */}
              <div className="bg-white rounded-card border border-line p-6 md:p-8 shadow-card flex flex-col md:flex-row items-start md:items-center justify-between gap-6 relative overflow-hidden">
                <div className="absolute top-0 left-0 w-2 h-full bg-gradient-to-b from-brand via-teal to-violet" />

                <div className="flex items-center gap-5">
                  <div className="w-16 h-16 rounded-card bg-gradient-to-tr from-navy to-brand flex items-center justify-center text-white font-semibold text-2xl shadow-pop border-2 border-white flex-shrink-0">
                    PR
                  </div>
                  <div>
                    <div className="flex items-center gap-2.5">
                      <h2 className="text-xl font-semibold text-ink">{data.student.name}</h2>
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-caption font-semibold bg-success-soft text-success border border-success-line">
                        <CheckCircle2 className="w-3 h-3" />
                        {language === "ta" ? "சரிபார்க்கப்பட்டது" : "Verified Profile"}
                      </span>
                    </div>
                    <p className="text-xs text-muted mt-1 font-medium">
                      B.Tech {data.student.branch} · Semester {data.student.semester} · {data.student.college}
                    </p>
                    <div className="flex items-center gap-3 mt-3">
                      <a
                        href={data.student.github_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1.5 text-xs text-ink-soft hover:text-ink font-medium bg-line-soft px-2.5 py-1 rounded-tile transition"
                      >
                        <FolderGit2 className="w-3.5 h-3.5" />
                        <span>github.com/priya-r</span>
                      </a>
                      <a
                        href={data.student.resume_url}
                        className="inline-flex items-center gap-1.5 text-xs text-brand hover:underline font-semibold"
                      >
                        <FileText className="w-3.5 h-3.5" />
                        <span>Resume (PDF)</span>
                      </a>
                    </div>
                  </div>
                </div>

                {/* Readiness Score Pill */}
                <div className="flex items-center gap-4 bg-surface-2 border border-line p-4 rounded-card">
                  <div className="text-right">
                    <div className="text-caption font-semibold text-muted">
                      {language === "ta" ? "வேலைவாய்ப்புத் தயார்நிலை" : "Placement Readiness"}
                    </div>
                    <div className="text-2xl font-semibold text-ink flex items-baseline justify-end gap-1">
                      <span>{data.student.readiness_score}</span>
                      <span className="text-xs font-semibold text-subtle">/ 100</span>
                    </div>
                  </div>
                  <div className="w-10 h-10 rounded-full bg-warning-soft text-warning border border-warning-line flex items-center justify-center font-semibold text-sm shadow-card">
                    ★
                  </div>
                </div>
              </div>

              {/* KPI Strip */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-white rounded-card border border-line p-4 shadow-card flex items-center gap-3.5">
                  <div className="w-10 h-10 rounded-card bg-brand-soft text-brand flex items-center justify-center">
                    <FolderGit2 className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-lg font-semibold text-ink">{data.stats.total_projects}</div>
                    <div className="text-caption text-muted font-medium">{t("portfolio.stat_deployed")}</div>
                  </div>
                </div>

                <div className="bg-white rounded-card border border-line p-4 shadow-card flex items-center gap-3.5">
                  <div className="w-10 h-10 rounded-card bg-success-faint text-success flex items-center justify-center">
                    <Sparkles className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-lg font-semibold text-ink">{data.stats.problems_solved}</div>
                    <div className="text-caption text-muted font-medium">{t("portfolio.stat_solved")}</div>
                  </div>
                </div>

                <div className="bg-white rounded-card border border-line p-4 shadow-card flex items-center gap-3.5">
                  <div className="w-10 h-10 rounded-card bg-violet-soft text-violet flex items-center justify-center">
                    <Award className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-lg font-semibold text-ink">{data.stats.verified_skills_count}</div>
                    <div className="text-caption text-muted font-medium">{t("portfolio.stat_badges")}</div>
                  </div>
                </div>

                <div className="bg-white rounded-card border border-line p-4 shadow-card flex items-center gap-3.5">
                  <div className="w-10 h-10 rounded-card bg-warning-faint text-warning flex items-center justify-center">
                    <Star className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-lg font-semibold text-ink">{data.stats.avg_project_score}%</div>
                    <div className="text-caption text-muted font-medium">{t("portfolio.stat_score")}</div>
                  </div>
                </div>
              </div>

              {/* Projects Showcase & Category Tabs */}
              <div className="space-y-5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-line pb-3">
                  <div className="flex items-center gap-2 overflow-x-auto scrollbar-none py-1">
                    {[
                      { id: "all", label: t("portfolio.filter_all") },
                      { id: "featured", label: t("portfolio.filter_featured") },
                      { id: "machine_learning", label: t("portfolio.filter_ml") },
                      { id: "fullstack", label: t("portfolio.filter_fullstack") },
                      { id: "iot", label: t("portfolio.filter_iot") }
                    ].map((tab) => (
                      <button
                        key={tab.id}
                        onClick={() => setActiveFilter(tab.id)}
                        className={`px-3 py-1.5 rounded-tile text-xs font-semibold whitespace-nowrap transition cursor-pointer ${
                          activeFilter === tab.id
                            ? "bg-brand text-white shadow-card"
                            : "bg-white text-muted hover:text-ink hover:bg-line/50 border border-line"
                        }`}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>

                  <span className="text-xs text-subtle font-semibold self-end sm:self-auto">
                    {filteredProjects.length} {language === "ta" ? "திட்டப்பணிகள்" : "Projects"}
                  </span>
                </div>

                {/* Empty State */}
                {filteredProjects.length === 0 ? (
                  <div className="bg-white rounded-card border border-dashed border-line-strong p-12 text-center space-y-4">
                    <Briefcase className="w-12 h-12 text-subtle mx-auto" />
                    <div>
                      <h4 className="text-base font-semibold text-ink">{t("portfolio.no_projects")}</h4>
                      <p className="text-xs text-muted mt-1 max-w-md mx-auto">{t("portfolio.no_projects_desc")}</p>
                    </div>
                    <button
                      onClick={openCreateModal}
                      className="px-4 py-2 bg-brand hover:bg-brand-hover text-white text-xs font-semibold rounded-card transition cursor-pointer"
                    >
                      {t("portfolio.add_project")}
                    </button>
                  </div>
                ) : (
                  /* Projects Grid */
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {filteredProjects.map((proj) => (
                      <div
                        key={proj.id}
                        className="bg-white rounded-card border border-line p-6 shadow-card hover:shadow-pop transition-all flex flex-col justify-between space-y-5 relative"
                      >
                        <div className="space-y-3">
                          {/* Card Header Pills */}
                          <div className="flex items-center justify-between gap-2 flex-wrap">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="text-caption font-semibold px-2 py-0.5 rounded-full bg-violet-soft text-violet">
                                {proj.category.replace("_", " ")}
                              </span>
                              {proj.is_featured && (
                                <span className="inline-flex items-center gap-1 text-caption font-semibold px-2 py-0.5 rounded-full bg-warning-soft text-warning">
                                  <Star className="w-3 h-3 fill-current" />
                                  {language === "ta" ? "சிறப்பு" : "Featured"}
                                </span>
                              )}
                              <span className="text-caption font-semibold px-2 py-0.5 rounded-full bg-success-soft text-success border border-success-line">
                                {proj.status === "deployed" ? t("portfolio.status_deployed") : proj.status}
                              </span>
                            </div>

                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => openEditModal(proj)}
                                title={t("portfolio.edit_project")}
                                className="p-1.5 rounded-tile text-muted hover:text-brand hover:bg-line-soft transition cursor-pointer"
                              >
                                <Edit3 className="w-4 h-4" />
                              </button>
                              <button
                                onClick={() => handleDeleteProject(proj.id)}
                                title={t("portfolio.delete_project")}
                                className="p-1.5 rounded-tile text-muted hover:text-danger hover:bg-danger-faint transition cursor-pointer"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </div>

                          {/* Title & Description */}
                          <div>
                            <h3 className="text-base font-semibold text-ink hover:text-brand transition">
                              {proj.title}
                            </h3>
                            <p className="text-xs text-muted mt-1.5 leading-relaxed">
                              {proj.description}
                            </p>
                          </div>

                          {/* Team & Role Pill */}
                          {proj.role_description && (
                            <div className="bg-surface-2 rounded-tile p-2.5 border border-line text-caption text-ink-soft">
                              <span className="font-semibold text-ink">{t("portfolio.team_role")}: </span>
                              <span>{proj.role_description} ({proj.team_name} · Team of {proj.team_size})</span>
                            </div>
                          )}

                          {/* Tech Stack Chips */}
                          <div className="flex flex-wrap gap-1.5 pt-1">
                            {proj.tech_stack.map((tech, idx) => (
                              <span
                                key={idx}
                                className="text-caption font-medium px-2 py-0.5 bg-line-soft text-ink-soft rounded-tile border border-line"
                              >
                                {tech}
                              </span>
                            ))}
                          </div>

                          {/* Trainer Verification Box */}
                          {proj.trainer_verified && (
                            <div className="bg-success-faint border border-success-line rounded-card p-3 text-caption space-y-1">
                              <div className="flex items-center justify-between text-success font-semibold">
                                <span className="flex items-center gap-1">
                                  <ShieldCheck className="w-3.5 h-3.5" />
                                  <span>{t("portfolio.verified_badge")}</span>
                                </span>
                                <span>Score: {proj.score_percent}%</span>
                              </div>
                              {proj.trainer_feedback && (
                                <p className="text-success italic">
                                  &ldquo;{proj.trainer_feedback}&rdquo; — {proj.trainer_name}
                                </p>
                              )}
                            </div>
                          )}
                        </div>

                        {/* Action Links */}
                        <div className="flex items-center gap-3 pt-3 border-t border-line">
                          <a
                            href={proj.github_url}
                            target="_blank"
                            rel="noreferrer"
                            className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 bg-line-soft hover:bg-line text-ink text-xs font-semibold rounded-card transition"
                          >
                            <FolderGit2 className="w-4 h-4" />
                            <span>{t("portfolio.github_repo")}</span>
                          </a>

                          {proj.live_demo_url && (
                            <a
                              href={proj.live_demo_url}
                              target="_blank"
                              rel="noreferrer"
                              className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 bg-teal hover:bg-teal-hover text-white text-xs font-semibold rounded-card shadow-card transition"
                            >
                              <ExternalLink className="w-4 h-4" />
                              <span>{t("portfolio.live_demo")}</span>
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Verified Technical Skills Section */}
              <div className="bg-white rounded-card border border-line p-6 shadow-card space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-semibold text-ink flex items-center gap-2">
                    <Award className="w-5 h-5 text-brand" />
                    <span>{t("portfolio.verified_skills")}</span>
                  </h3>
                  <span className="text-xs text-muted font-medium">
                    {data.verified_skills.length} {language === "ta" ? "சரிபார்க்கப்பட்ட திறன்கள்" : "Verified Badges"}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {data.verified_skills.map((skill) => (
                    <div
                      key={skill.id}
                      className="border border-line rounded-card p-4 bg-surface-2 flex items-start justify-between gap-3"
                    >
                      <div>
                        <div className="text-xs font-semibold text-ink">{skill.skill_name}</div>
                        <div className="text-caption text-muted mt-0.5">{skill.category}</div>
                        <div className="text-caption text-success font-medium mt-2 flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>{t("portfolio.verified_by")} {skill.verified_by}</span>
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <span className="text-caption font-semibold px-2 py-0.5 rounded-full bg-warning-soft text-warning border border-warning-line">
                          {skill.level}
                        </span>
                        <span className="text-caption text-subtle font-semibold">
                          {skill.problems_solved} {t("portfolio.problems_solved_count")}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Certifications Section */}
              <div className="bg-white rounded-card border border-line p-6 shadow-card space-y-4">
                <h3 className="text-base font-semibold text-ink flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-success" />
                  <span>{t("portfolio.certifications")}</span>
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {data.certifications.map((cert, idx) => (
                    <div
                      key={idx}
                      className="border border-line rounded-card p-4 bg-white hover:border-line-strong transition shadow-card flex flex-col justify-between space-y-3"
                    >
                      <div>
                        <div className="text-xs font-semibold text-ink leading-snug">{cert.title}</div>
                        <div className="text-caption text-muted mt-1">{cert.issuer}</div>
                      </div>
                      <div className="flex items-center justify-between pt-2 border-t border-line-soft">
                        <span className="text-caption font-semibold text-muted">{cert.status}</span>
                        <span className="text-caption font-semibold text-brand">{cert.score}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Add / Edit Project Modal */}
          {isModalOpen && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs overflow-y-auto">
              <div className="bg-white rounded-card border border-line max-w-xl w-full p-6 shadow-pop relative my-8">
                <button
                  onClick={() => setIsModalOpen(false)}
                  className="absolute top-5 right-5 p-1 rounded-tile text-muted hover:text-ink hover:bg-line-soft transition cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>

                <h3 className="text-lg font-semibold text-ink mb-1">
                  {editingProject ? t("portfolio.modal_edit_title") : t("portfolio.modal_title")}
                </h3>
                <p className="text-xs text-muted mb-5">
                  {language === "ta"
                    ? "திட்டப்பணி தகவல்களை உள்ளிட்டு சேமிக்கவும். இது வேலைவாய்ப்பு செல் மதிப்பாய்வு செய்யப்படும்."
                    : "Enter project specifications and repository URLs to update your verified portfolio."}
                </p>

                {formError && (
                  <div className="mb-4 p-3 rounded-card bg-danger-faint border border-danger-line text-xs text-danger">
                    {formError}
                  </div>
                )}

                <form onSubmit={handleSaveProject} className="space-y-4 text-xs">
                  <div>
                    <label className="block font-semibold text-ink mb-1">
                      {t("portfolio.form_title")} *
                    </label>
                    <input
                      type="text"
                      required
                      value={formTitle}
                      onChange={(e) => setFormTitle(e.target.value)}
                      placeholder="e.g. Smart City Traffic Optimizer"
                      className="w-full px-3 py-2 rounded-card border border-line-strong focus:outline-none focus:border-brand text-xs"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block font-semibold text-ink mb-1">
                        {t("portfolio.form_category")}
                      </label>
                      <select
                        value={formCategory}
                        onChange={(e) => setFormCategory(e.target.value)}
                        className="w-full px-3 py-2 rounded-card border border-line-strong focus:outline-none focus:border-brand text-xs bg-white"
                      >
                        <option value="machine_learning">Machine Learning & AI</option>
                        <option value="fullstack">Full-Stack Web</option>
                        <option value="iot">IoT & Embedded Systems</option>
                        <option value="cloud">Cloud & DevOps</option>
                      </select>
                    </div>

                    <div>
                      <label className="block font-semibold text-ink mb-1">
                        {language === "ta" ? "குழு அளவு" : "Team Size"}
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="10"
                        value={formTeamSize}
                        onChange={(e) => setFormTeamSize(Number(e.target.value))}
                        className="w-full px-3 py-2 rounded-card border border-line-strong focus:outline-none focus:border-brand text-xs"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block font-semibold text-ink mb-1">
                      {t("portfolio.form_desc")} *
                    </label>
                    <textarea
                      rows={3}
                      required
                      value={formDescription}
                      onChange={(e) => setFormDescription(e.target.value)}
                      placeholder="Explain problem statement, architecture, dataset, and engineering outcomes..."
                      className="w-full px-3 py-2 rounded-card border border-line-strong focus:outline-none focus:border-brand text-xs"
                    />
                  </div>

                  <div>
                    <label className="block font-semibold text-ink mb-1">
                      {t("portfolio.form_role")}
                    </label>
                    <input
                      type="text"
                      value={formRole}
                      onChange={(e) => setFormRole(e.target.value)}
                      placeholder="e.g. Lead Developer, Backend API & Model Training"
                      className="w-full px-3 py-2 rounded-card border border-line-strong focus:outline-none focus:border-brand text-xs"
                    />
                  </div>

                  <div>
                    <label className="block font-semibold text-ink mb-1">
                      {t("portfolio.form_stack")}
                    </label>
                    <input
                      type="text"
                      value={formTechStack}
                      onChange={(e) => setFormTechStack(e.target.value)}
                      placeholder="e.g. Python, FastAPI, React, Docker, Postgres"
                      className="w-full px-3 py-2 rounded-card border border-line-strong focus:outline-none focus:border-brand text-xs"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block font-semibold text-ink mb-1">
                        {t("portfolio.form_github")} *
                      </label>
                      <input
                        type="url"
                        required
                        value={formGithubUrl}
                        onChange={(e) => setFormGithubUrl(e.target.value)}
                        placeholder="https://github.com/priya-r/my-project"
                        className="w-full px-3 py-2 rounded-card border border-line-strong focus:outline-none focus:border-brand text-xs"
                      />
                    </div>

                    <div>
                      <label className="block font-semibold text-ink mb-1">
                        {t("portfolio.form_demo")}
                      </label>
                      <input
                        type="url"
                        value={formLiveDemoUrl}
                        onChange={(e) => setFormLiveDemoUrl(e.target.value)}
                        placeholder="https://my-demo.example.com"
                        className="w-full px-3 py-2 rounded-card border border-line-strong focus:outline-none focus:border-brand text-xs"
                      />
                    </div>
                  </div>

                  <div className="flex items-center gap-2 pt-2">
                    <input
                      type="checkbox"
                      id="feat_check"
                      checked={formIsFeatured}
                      onChange={(e) => setFormIsFeatured(e.target.checked)}
                      className="rounded border-line-strong text-brand focus:ring-0 cursor-pointer"
                    />
                    <label htmlFor="feat_check" className="text-xs text-ink font-semibold cursor-pointer">
                      {language === "ta" ? "சிறப்பு திட்டப்பணியாக முன்னிலைப்படுத்து" : "Mark as Featured Project on Top Banner"}
                    </label>
                  </div>

                  <div className="flex items-center justify-end gap-3 pt-4 border-t border-line">
                    <button
                      type="button"
                      onClick={() => setIsModalOpen(false)}
                      className="px-4 py-2 rounded-card border border-line-strong text-ink-soft hover:bg-line-soft font-semibold text-xs transition cursor-pointer"
                    >
                      {t("portfolio.form_cancel")}
                    </button>
                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="px-5 py-2 rounded-card bg-brand hover:bg-brand-hover text-white font-semibold text-xs shadow-card transition cursor-pointer disabled:opacity-50"
                    >
                      {isSubmitting ? t("portfolio.saving") : t("portfolio.form_save")}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
