"use client";

import {
  Activity,
  ArrowLeft,
  Download,
  History,
  Loader2,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { ReconstructionDrawer } from "@/components/studio/ReconstructionDrawer";
import { SectionEditorCard } from "@/components/studio/SectionEditorCard";
import { DocTypeBadge, StatusBadge } from "@/components/ui/Badges";
import { Navbar } from "@/components/ui/Navbar";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { DocumentSection, ProjectDetail } from "@/lib/types";

export default function ProjectStudioPage() {
  const params = useParams<{ id: string }>();
  const projectId = params?.id;
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [activeSectionId, setActiveSectionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadProject = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const detail = await api.getProject(projectId);
      setProject(detail);
      if (detail.sections.length > 0) {
        setActiveSectionId((prev) => prev || detail.sections[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load project.");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
    }
  }, [authLoading, user, router]);

  useEffect(() => {
    if (user && projectId) {
      void loadProject();
    }
  }, [user, projectId, loadProject]);

  const handleGenerateAll = async () => {
    if (!project) return;
    setGenerating(true);
    setError(null);
    try {
      const updated = await api.generateProject(project.id, {
        generate_images: project.theme_config_json?.include_images ?? true,
      });
      setProject(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed.");
    } finally {
      setGenerating(false);
    }
  };

  const handleExport = async () => {
    if (!project) return;
    setExporting(true);
    setError(null);
    try {
      const { blob, filename } = await api.downloadExport(project.id, project.doc_type);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed.");
    } finally {
      setExporting(false);
    }
  };

  const handleSectionUpdated = (updatedSection: DocumentSection) => {
    setProject((prev) =>
      prev
        ? {
            ...prev,
            current_version: prev.current_version + 1,
            sections: prev.sections.map((s) => (s.id === updatedSection.id ? updatedSection : s)),
          }
        : prev
    );
  };

  const scrollToSection = (sectionId: string) => {
    setActiveSectionId(sectionId);
    const el = document.getElementById(`section-${sectionId}`);
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="min-h-screen bg-[#f7f8fa]">
      <Navbar />

      {loading ? (
        <div className="mx-auto max-w-7xl px-4 py-16 text-center text-sm text-slate-500">
          <Loader2 className="mx-auto mb-3 h-6 w-6 animate-spin text-teal-700" />
          Loading document studio...
        </div>
      ) : !project ? (
        <div className="mx-auto max-w-xl px-4 py-16 text-center">
          <div className="rounded-2xl border border-rose-200 bg-white p-8">
            <h1 className="font-editorial text-2xl font-semibold text-rose-700">Project Unavailable</h1>
            <p className="mt-2 text-sm text-slate-600">{error || "Project could not be loaded."}</p>
            <Link
              href="/dashboard"
              className="mt-6 inline-flex items-center gap-2 rounded-xl bg-[#0f2942] px-4 py-2 text-sm font-semibold text-white"
            >
              Back to Dashboard
            </Link>
          </div>
        </div>
      ) : (
        <>
          {/* Sticky Studio Toolbar */}
          <div className="sticky top-16 z-30 border-b border-slate-200 bg-white/95 backdrop-blur-sm">
            <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-3.5 sm:px-6 lg:px-8">
              <div className="flex items-center gap-3">
                <Link
                  href="/dashboard"
                  className="rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-100"
                  title="Back to Dashboard"
                >
                  <ArrowLeft className="h-4 w-4" />
                </Link>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h1 className="font-editorial text-xl font-semibold text-[#0f2942] sm:text-2xl">
                      {project.title}
                    </h1>
                    <DocTypeBadge docType={project.doc_type} />
                    <StatusBadge status={project.status} />
                    <span className="font-mono-code rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                      v{project.current_version}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 line-clamp-1">{project.main_topic}</p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={handleGenerateAll}
                  disabled={generating}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-teal-300 bg-teal-50 px-3.5 py-2 text-xs font-semibold text-teal-800 hover:bg-teal-100 disabled:opacity-60"
                >
                  {generating ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="h-3.5 w-3.5" />
                  )}
                  {generating
                    ? "Generating..."
                    : project.sections.some((s) => s.current_content_json)
                    ? "Regenerate All"
                    : "Generate Content"}
                </button>

                <button
                  type="button"
                  onClick={() => setHistoryOpen(true)}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                >
                  <History className="h-3.5 w-3.5" />
                  History & Reconstruct
                </button>

                <Link
                  href={`/monitoring?project_id=${project.id}`}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                >
                  <Activity className="h-3.5 w-3.5" />
                  Logs
                </Link>

                <button
                  type="button"
                  onClick={handleExport}
                  disabled={exporting}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-[#0f2942] px-4 py-2 text-xs font-semibold text-white shadow-xs transition hover:bg-[#173b5e] disabled:opacity-60"
                >
                  {exporting ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Download className="h-3.5 w-3.5" />
                  )}
                  Export .{project.doc_type}
                </button>
              </div>
            </div>
          </div>

          <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
            {error && (
              <div role="alert" className="mb-6 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                {error}
              </div>
            )}

            <div className="grid gap-8 lg:grid-cols-12">
              {/* Left Outline Navigator */}
              <aside className="lg:col-span-3">
                <div className="sticky top-36 rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
                  <div className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">
                    {project.doc_type === "pptx" ? "Slide Deck Navigator" : "Document Outline"}
                  </div>
                  <nav className="space-y-1.5">
                    {project.sections.map((sec, idx) => (
                      <button
                        key={sec.id}
                        type="button"
                        onClick={() => scrollToSection(sec.id)}
                        className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-xs transition ${
                          activeSectionId === sec.id
                            ? "bg-[#0f2942] text-white"
                            : "text-slate-700 hover:bg-slate-100"
                        }`}
                      >
                        <span className="truncate font-medium">
                          <span className="font-mono-code mr-1.5 opacity-75">{idx + 1}.</span>
                          {sec.title}
                        </span>
                        <span className="ml-2 flex shrink-0 items-center gap-1 text-[10px]">
                          {sec.like_status === "like" && "👍"}
                          {sec.like_status === "dislike" && "👎"}
                          {sec.comments.length > 0 && (
                            <span className="rounded bg-black/15 px-1">{sec.comments.length}</span>
                          )}
                        </span>
                      </button>
                    ))}
                  </nav>
                </div>
              </aside>

              {/* Main Editor Canvas */}
              <div className="space-y-6 lg:col-span-9">
                {project.sections.map((sec, idx) => (
                  <SectionEditorCard
                    key={sec.id}
                    docType={project.doc_type}
                    section={sec}
                    index={idx}
                    onSectionUpdated={handleSectionUpdated}
                  />
                ))}
              </div>
            </div>
          </main>

          <ReconstructionDrawer
            projectId={project.id}
            open={historyOpen}
            onClose={() => setHistoryOpen(false)}
            onRestored={loadProject}
          />
        </>
      )}
    </div>
  );
}
