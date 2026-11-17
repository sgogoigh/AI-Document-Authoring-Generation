"use client";

import {
  ArrowUpRight,
  Download,
  FileSpreadsheet,
  FileText,
  Layers,
  Plus,
  Search,
  Sparkles,
  ThumbsUp,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { DocTypeBadge, StatusBadge } from "@/components/ui/Badges";
import { Navbar } from "@/components/ui/Navbar";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { ProjectSummary } from "@/lib/types";

export default function DashboardPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [docTypeFilter, setDocTypeFilter] = useState<"" | "docx" | "pptx">("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await api.listProjects({
        doc_type: docTypeFilter || undefined,
        search: search.trim() || undefined,
      });
      setProjects(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects.");
    } finally {
      setLoading(false);
    }
  }, [docTypeFilter, search]);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
    }
  }, [authLoading, user, router]);

  useEffect(() => {
    if (user) {
      void loadProjects();
    }
  }, [user, loadProjects]);

  const handleDelete = async (id: string) => {
    try {
      await api.deleteProject(id);
      setConfirmDeleteId(null);
      setProjects((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete project.");
    }
  };

  const handleQuickExport = async (project: ProjectSummary) => {
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
      void loadProjects();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed.");
    }
  };

  const totalExports = projects.reduce((sum, p) => sum + p.export_count, 0);
  const totalLikes = projects.reduce((sum, p) => sum + p.like_count, 0);
  const docxCount = projects.filter((p) => p.doc_type === "docx").length;
  const pptxCount = projects.filter((p) => p.doc_type === "pptx").length;

  return (
    <div className="min-h-screen bg-[#f7f8fa]">
      <Navbar />

      <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-teal-700">Workspace</p>
            <h1 className="font-editorial text-3xl font-semibold text-[#0f2942] sm:text-4xl">
              Your Document Projects
            </h1>
            <p className="mt-1 text-sm text-slate-600">
              Create, refine, reconstruct, and export structured Word reports and PowerPoint decks.
            </p>
          </div>
          <Link
            href="/projects/new"
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#0f2942] px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-[#173b5e]"
          >
            <Plus className="h-4 w-4" />
            New Document Project
          </Link>
        </div>

        {/* Summary KPI Strip */}
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { label: "Total Projects", value: projects.length, icon: Layers, accent: "text-[#0f2942]" },
            { label: "Word / PowerPoint", value: `${docxCount} / ${pptxCount}`, icon: FileText, accent: "text-sky-700" },
            { label: "Section Likes", value: totalLikes, icon: ThumbsUp, accent: "text-emerald-700" },
            { label: "Completed Exports", value: totalExports, icon: Download, accent: "text-teal-700" },
          ].map((stat) => {
            const Icon = stat.icon;
            return (
              <div key={stat.label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    {stat.label}
                  </span>
                  <Icon className={`h-4 w-4 ${stat.accent}`} />
                </div>
                <div className={`mt-2 text-2xl font-bold ${stat.accent}`}>{stat.value}</div>
              </div>
            );
          })}
        </div>

        {/* Filter & Search Bar */}
        <div className="mt-8 flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-xs sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-1.5">
            {(
              [
                { value: "", label: "All Formats" },
                { value: "docx", label: "Word (.docx)" },
                { value: "pptx", label: "PowerPoint (.pptx)" },
              ] as const
            ).map((tab) => (
              <button
                key={tab.label}
                type="button"
                onClick={() => setDocTypeFilter(tab.value)}
                className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
                  docTypeFilter === tab.value
                    ? "bg-[#0f2942] text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="relative w-full sm:w-72">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by title or topic..."
              className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-sm text-slate-800 outline-none transition focus:border-[#0d9488] focus:bg-white"
            />
          </div>
        </div>

        {error && (
          <div role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        {/* Project Cards */}
        {loading ? (
          <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((idx) => (
              <div key={idx} className="h-52 animate-pulse rounded-2xl border border-slate-200 bg-white p-6" />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <div className="mt-10 rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-teal-50 text-teal-700">
              <Sparkles className="h-6 w-6" />
            </div>
            <h2 className="mt-4 font-editorial text-2xl font-semibold text-[#0f2942]">
              No document projects yet
            </h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-slate-600">
              Launch your first Word report or PowerPoint deck and try AI-Suggest Outline to scaffold structure in seconds.
            </p>
            <Link
              href="/projects/new"
              className="mt-6 inline-flex items-center gap-2 rounded-xl bg-[#0f2942] px-5 py-2.5 text-sm font-semibold text-white"
            >
              <Plus className="h-4 w-4" />
              Create First Project
            </Link>
          </div>
        ) : (
          <div className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((proj) => (
              <div
                key={proj.id}
                className="flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-6 shadow-xs transition hover:border-teal-300 hover:shadow-md"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <DocTypeBadge docType={proj.doc_type} />
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono-code rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600">
                        v{proj.current_version}
                      </span>
                      <StatusBadge status={proj.status} />
                    </div>
                  </div>

                  <Link href={`/projects/${proj.id}`} className="group mt-4 block">
                    <h2 className="font-editorial text-xl font-semibold text-[#0f2942] group-hover:text-[#0d9488] line-clamp-1">
                      {proj.title}
                    </h2>
                    <p className="mt-1.5 text-sm text-slate-600 line-clamp-2">{proj.main_topic}</p>
                  </Link>
                </div>

                <div className="mt-5 border-t border-slate-100 pt-4">
                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <span className="inline-flex items-center gap-1 font-medium">
                      {proj.doc_type === "pptx" ? (
                        <FileSpreadsheet className="h-3.5 w-3.5" />
                      ) : (
                        <FileText className="h-3.5 w-3.5" />
                      )}
                      {proj.section_count} {proj.doc_type === "pptx" ? "slides" : "sections"}
                    </span>
                    <span>
                      👍 {proj.like_count} • 👎 {proj.dislike_count} • Exports {proj.export_count}
                    </span>
                  </div>

                  <div className="mt-3 flex items-center justify-between gap-2">
                    <Link
                      href={`/projects/${proj.id}`}
                      className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-[#0f2942] px-3 py-2 text-xs font-semibold text-white transition hover:bg-[#173b5e]"
                    >
                      Open Studio
                      <ArrowUpRight className="h-3.5 w-3.5" />
                    </Link>

                    <button
                      type="button"
                      onClick={() => handleQuickExport(proj)}
                      title="Export document"
                      className="rounded-xl border border-slate-200 bg-white p-2 text-slate-700 transition hover:bg-slate-50 hover:text-teal-700"
                    >
                      <Download className="h-4 w-4" />
                    </button>

                    {confirmDeleteId === proj.id ? (
                      <button
                        type="button"
                        onClick={() => handleDelete(proj.id)}
                        className="rounded-xl bg-rose-600 px-2.5 py-2 text-xs font-semibold text-white"
                      >
                        Confirm
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setConfirmDeleteId(proj.id)}
                        title="Delete project"
                        className="rounded-xl border border-slate-200 bg-white p-2 text-slate-500 transition hover:bg-rose-50 hover:text-rose-600"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
