"use client";

import {
  Activity,
  ChevronDown,
  ChevronRight,
  Cpu,
  Download,
  History,
  Loader2,
  Search,
  ThumbsUp,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Fragment, Suspense, useCallback, useEffect, useState } from "react";

import { Navbar } from "@/components/ui/Navbar";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type {
  AuditLogItem,
  MonitoringMetrics,
  ProjectSummary,
  ReconstructionResult,
} from "@/lib/types";

function MonitoringConsoleContent() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialProjectId = searchParams.get("project_id") || "";

  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState(initialProjectId);
  const [eventTypeFilter, setEventTypeFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [searchFilter, setSearchFilter] = useState("");

  const [metrics, setMetrics] = useState<MonitoringMetrics | null>(null);
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [totalLogs, setTotalLogs] = useState(0);
  const [expandedSeqId, setExpandedSeqId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  // Reconstruction Workbench
  const [reconProjectId, setReconProjectId] = useState(initialProjectId);
  const [reconVersion, setReconVersion] = useState<string>("1");
  const [reconResult, setReconResult] = useState<ReconstructionResult | null>(null);
  const [reconLoading, setReconLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
    }
  }, [authLoading, user, router]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [projList, metricsData, logsData] = await Promise.all([
        api.listProjects(),
        api.getMonitoringMetrics(selectedProjectId || undefined),
        api.getAuditLogs({
          project_id: selectedProjectId || undefined,
          event_type: eventTypeFilter || undefined,
          severity: severityFilter || undefined,
          search: searchFilter.trim() || undefined,
          limit: 50,
        }),
      ]);
      setProjects(projList);
      if (!reconProjectId && projList.length > 0) {
        setReconProjectId(projList[0].id);
      }
      setMetrics(metricsData);
      setLogs(logsData.items);
      setTotalLogs(logsData.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load monitoring data.");
    } finally {
      setLoading(false);
    }
  }, [selectedProjectId, eventTypeFilter, severityFilter, searchFilter, reconProjectId]);

  useEffect(() => {
    if (user) {
      void loadData();
    }
  }, [user, loadData]);

  const handleReconstruct = async () => {
    if (!reconProjectId) return;
    setReconLoading(true);
    setError(null);
    try {
      const res = await api.reconstructProject(reconProjectId, {
        version: Math.max(1, Number(reconVersion) || 1),
      });
      setReconResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reconstruction query failed.");
    } finally {
      setReconLoading(false);
    }
  };

  const llm = metrics?.analytics.llm;
  const feedback = metrics?.analytics.feedback;

  return (
    <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8 space-y-8">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-teal-700">
          Observability & Audit
        </p>
        <h1 className="font-editorial text-3xl font-semibold text-[#0f2942] sm:text-4xl">
          Database Monitoring, Telemetry & Reconstruction
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Filter immutable audit logs, analyze Gemini token & latency metrics, and reconstruct any project snapshot.
        </p>
      </div>

      {error && (
        <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-semibold uppercase text-slate-500">
            <span>Gemini LLM Calls</span>
            <Cpu className="h-4 w-4 text-[#0f2942]" />
          </div>
          <div className="mt-2 text-2xl font-bold text-[#0f2942]">{llm?.total_calls ?? 0}</div>
          <div className="mt-1 font-mono-code text-xs text-slate-500">
            Tokens: {(llm?.total_tokens ?? 0).toLocaleString()} • Error {llm?.error_rate ?? 0}%
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-semibold uppercase text-slate-500">
            <span>Latency (Avg / p95)</span>
            <Activity className="h-4 w-4 text-teal-700" />
          </div>
          <div className="mt-2 text-2xl font-bold text-teal-700">
            {llm ? `${Math.round(llm.avg_latency_ms)} ms` : "0 ms"}
          </div>
          <div className="mt-1 font-mono-code text-xs text-slate-500">
            p50: {llm ? Math.round(llm.p50_latency_ms) : 0} ms • p95:{" "}
            {llm ? Math.round(llm.p95_latency_ms) : 0} ms
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-semibold uppercase text-slate-500">
            <span>User Satisfaction</span>
            <ThumbsUp className="h-4 w-4 text-emerald-700" />
          </div>
          <div className="mt-2 text-2xl font-bold text-emerald-700">
            {feedback?.satisfaction_rate_pct !== null && feedback?.satisfaction_rate_pct !== undefined
              ? `${feedback.satisfaction_rate_pct}%`
              : "N/A"}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            👍 {feedback?.like_count ?? 0} likes • 👎 {feedback?.dislike_count ?? 0} dislikes
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-semibold uppercase text-slate-500">
            <span>Audit Events & Exports</span>
            <Download className="h-4 w-4 text-indigo-700" />
          </div>
          <div className="mt-2 text-2xl font-bold text-indigo-700">
            {metrics?.analytics.audit.total_events ?? 0}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            Completed document exports: {metrics?.analytics.exports.total_exports ?? 0}
          </div>
        </div>
      </div>

      {/* Point-in-Time Reconstruction Workbench */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <History className="h-5 w-5 text-teal-700" />
            <div>
              <h2 className="font-editorial text-xl font-semibold text-[#0f2942]">
                Project State Reconstruction Workbench
              </h2>
              <p className="text-xs text-slate-500">
                Reconstruct any project version directly from database snapshots & event history.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Select project for reconstruction"
              value={reconProjectId}
              onChange={(e) => setReconProjectId(e.target.value)}
              className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title} (v{p.current_version})
                </option>
              ))}
            </select>

            <input
              aria-label="Version number"
              type="number"
              min={1}
              value={reconVersion}
              onChange={(e) => setReconVersion(e.target.value)}
              className="w-20 rounded-xl border border-slate-300 px-3 py-2 text-xs font-semibold"
              placeholder="Ver"
            />

            <button
              type="button"
              onClick={handleReconstruct}
              disabled={reconLoading || !reconProjectId}
              className="inline-flex items-center gap-1.5 rounded-xl bg-[#0f2942] px-4 py-2 text-xs font-semibold text-white hover:bg-[#173b5e] disabled:opacity-50"
            >
              {reconLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <History className="h-3.5 w-3.5" />}
              Reconstruct State
            </button>
          </div>
        </div>

        {reconResult && (
          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-mono-code text-xs font-semibold text-[#0f2942]">
                {reconResult.reconstruction_mode} — {reconResult.reconstructed_state.title}
              </span>
              <span className="text-xs text-slate-600">
                {reconResult.diff_against_live.length} diff(s) vs live state
              </span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {reconResult.reconstructed_state.sections.map((s, idx) => (
                <div key={s.id} className="rounded-lg border border-slate-200 bg-white p-3 text-xs">
                  <div className="font-semibold text-[#0f2942]">
                    {idx + 1}. {s.title}
                  </div>
                  <p className="mt-1 text-slate-600 line-clamp-3">
                    {s.current_content_text || "(No generated content at this version)"}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Filterable Audit Event Stream */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="font-editorial text-xl font-semibold text-[#0f2942]">
              Filterable Audit Event Stream ({totalLogs})
            </h2>
            <p className="text-xs text-slate-500">
              Click any row to inspect trace IDs and before/after JSON payloads.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Filter by project"
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs"
            >
              <option value="">All Projects</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title}
                </option>
              ))}
            </select>

            <select
              aria-label="Filter by event type"
              value={eventTypeFilter}
              onChange={(e) => setEventTypeFilter(e.target.value)}
              className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs"
            >
              <option value="">All Events</option>
              <option value="AUTH_LOGIN">AUTH_LOGIN</option>
              <option value="AUTH_GOOGLE_LOGIN">AUTH_GOOGLE_LOGIN</option>
              <option value="PROJECT_CREATE">PROJECT_CREATE</option>
              <option value="OUTLINE_SUGGEST">OUTLINE_SUGGEST</option>
              <option value="CONTENT_GENERATE">CONTENT_GENERATE</option>
              <option value="SECTION_REFINE">SECTION_REFINE</option>
              <option value="FEEDBACK_RECORD">FEEDBACK_RECORD</option>
              <option value="COMMENT_CREATE">COMMENT_CREATE</option>
              <option value="DOC_EXPORT">DOC_EXPORT</option>
              <option value="PROJECT_RESTORE">PROJECT_RESTORE</option>
            </select>

            <select
              aria-label="Filter by severity"
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs"
            >
              <option value="">All Severities</option>
              <option value="INFO">INFO</option>
              <option value="WARN">WARN</option>
              <option value="ERROR">ERROR</option>
            </select>

            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400" />
              <input
                type="search"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder="Search trace or event..."
                className="rounded-xl border border-slate-300 py-1.5 pl-8 pr-3 text-xs outline-none focus:border-[#0d9488]"
              />
            </div>
          </div>
        </div>

        {loading ? (
          <div className="py-10 text-center text-sm text-slate-500">Loading telemetry...</div>
        ) : logs.length === 0 ? (
          <div className="py-10 text-center text-sm text-slate-500">
            No audit events match the active filters.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-3 py-2.5 font-semibold">Seq</th>
                  <th className="px-3 py-2.5 font-semibold">Event Type</th>
                  <th className="px-3 py-2.5 font-semibold">Severity</th>
                  <th className="px-3 py-2.5 font-semibold">Entity</th>
                  <th className="px-3 py-2.5 font-semibold">Trace ID</th>
                  <th className="px-3 py-2.5 font-semibold">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {logs.map((ev) => {
                  const isExpanded = expandedSeqId === ev.seq_id;
                  return (
                    <Fragment key={ev.seq_id}>
                      <tr
                        onClick={() => setExpandedSeqId(isExpanded ? null : ev.seq_id)}
                        className="cursor-pointer hover:bg-slate-50"
                      >
                        <td className="px-3 py-2.5 font-mono-code text-slate-500">
                          <span className="inline-flex items-center gap-1">
                            {isExpanded ? (
                              <ChevronDown className="h-3.5 w-3.5" />
                            ) : (
                              <ChevronRight className="h-3.5 w-3.5" />
                            )}
                            #{ev.seq_id}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 font-mono-code font-semibold text-[#0f2942]">
                          {ev.event_type}
                        </td>
                        <td className="px-3 py-2.5">
                          <span
                            className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                              ev.severity === "ERROR"
                                ? "bg-rose-100 text-rose-700"
                                : ev.severity === "WARN"
                                ? "bg-amber-100 text-amber-800"
                                : "bg-teal-50 text-teal-800"
                            }`}
                          >
                            {ev.severity}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-slate-600">{ev.entity_type}</td>
                        <td className="px-3 py-2.5 font-mono-code text-[11px] text-slate-500">
                          {ev.trace_id.slice(0, 12)}…
                        </td>
                        <td className="px-3 py-2.5 text-slate-500">
                          {new Date(ev.created_at).toLocaleString()}
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr key={`${ev.seq_id}-detail`} className="bg-slate-50/80">
                          <td colSpan={6} className="px-4 py-3">
                            <div className="grid gap-3 md:grid-cols-2 font-mono-code text-[11px]">
                              <div>
                                <div className="mb-1 font-bold text-slate-600">Before State</div>
                                <pre className="max-h-40 overflow-auto rounded-lg border border-slate-200 bg-white p-2 text-slate-700">
                                  {JSON.stringify(ev.before_state_json, null, 2)}
                                </pre>
                              </div>
                              <div>
                                <div className="mb-1 font-bold text-slate-600">After State & Metadata</div>
                                <pre className="max-h-40 overflow-auto rounded-lg border border-slate-200 bg-white p-2 text-slate-700">
                                  {JSON.stringify(
                                    { after: ev.after_state_json, metadata: ev.metadata_json },
                                    null,
                                    2
                                  )}
                                </pre>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Recent LLM Calls Table */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
        <h2 className="font-editorial text-xl font-semibold text-[#0f2942] mb-4">
          Recent Gemini API Telemetry ({metrics?.total_llm_records ?? 0})
        </h2>
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-3 py-2.5 font-semibold">Operation</th>
                <th className="px-3 py-2.5 font-semibold">Model</th>
                <th className="px-3 py-2.5 font-semibold">Tokens (In/Out/Total)</th>
                <th className="px-3 py-2.5 font-semibold">Latency</th>
                <th className="px-3 py-2.5 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {(metrics?.recent_llm_calls ?? []).map((m) => (
                <tr key={m.id}>
                  <td className="px-3 py-2.5 font-mono-code font-semibold text-[#0f2942]">
                    {m.operation}
                  </td>
                  <td className="px-3 py-2.5 font-mono-code text-slate-600">{m.model_name}</td>
                  <td className="px-3 py-2.5 font-mono-code text-slate-600">
                    {m.input_tokens} / {m.output_tokens} / <strong>{m.total_tokens}</strong>
                  </td>
                  <td className="px-3 py-2.5 font-mono-code text-slate-600">
                    {Math.round(m.latency_ms)} ms
                  </td>
                  <td className="px-3 py-2.5">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                        m.status === "success"
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-rose-100 text-rose-700"
                      }`}
                    >
                      {m.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}

export default function MonitoringPage() {
  return (
    <div className="min-h-screen bg-[#f7f8fa]">
      <Navbar />
      <Suspense
        fallback={
          <div className="py-16 text-center text-sm text-slate-500">Loading monitoring console...</div>
        }
      >
        <MonitoringConsoleContent />
      </Suspense>
    </div>
  );
}
