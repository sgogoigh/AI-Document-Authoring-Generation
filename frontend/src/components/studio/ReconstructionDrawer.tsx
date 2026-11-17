"use client";

import { History, Loader2, RotateCcw, X } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { ProjectTimeline, ReconstructionResult } from "@/lib/types";

export function ReconstructionDrawer({
  projectId,
  open,
  onClose,
  onRestored,
}: {
  projectId: string;
  open: boolean;
  onClose: () => void;
  onRestored: () => Promise<void>;
}) {
  const [timeline, setTimeline] = useState<ProjectTimeline | null>(null);
  const [reconstructed, setReconstructed] = useState<ReconstructionResult | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    api
      .getProjectTimeline(projectId)
      .then((tl) => {
        setTimeline(tl);
        if (tl.snapshots.length > 0) {
          const ver = tl.snapshots[0].version_number;
          setSelectedVersion(ver);
          return api.reconstructProject(projectId, { version: ver });
        }
        return null;
      })
      .then((rec) => {
        if (rec) setReconstructed(rec);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load timeline."))
      .finally(() => setLoading(false));
  }, [open, projectId]);

  const inspectVersion = async (version: number) => {
    setSelectedVersion(version);
    setLoading(true);
    setError(null);
    try {
      const rec = await api.reconstructProject(projectId, { version });
      setReconstructed(rec);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reconstruction failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleRestore = async () => {
    if (selectedVersion === null) return;
    setRestoring(true);
    setError(null);
    try {
      await api.restoreVersion(projectId, selectedVersion);
      await onRestored();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Restore failed.");
    } finally {
      setRestoring(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-xs">
      <div className="flex h-full w-full max-w-2xl flex-col bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <div className="flex items-center gap-2">
            <History className="h-5 w-5 text-teal-700" />
            <div>
              <h2 className="font-editorial text-xl font-semibold text-[#0f2942]">
                Project History & Reconstruction
              </h2>
              <p className="text-xs text-slate-500">
                Inspect point-in-time snapshots, field diffs, and restore non-destructively.
              </p>
            </div>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-xs text-rose-700">
              {error}
            </div>
          )}

          {timeline && (
            <div>
              <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">
                Captured Version Snapshots
              </h3>
              <div className="flex flex-wrap gap-2">
                {timeline.snapshots.map((snap) => (
                  <button
                    key={snap.id}
                    type="button"
                    onClick={() => inspectVersion(snap.version_number)}
                    className={`rounded-xl border px-3 py-2 text-left text-xs transition ${
                      selectedVersion === snap.version_number
                        ? "border-[#0f2942] bg-[#0f2942] text-white"
                        : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    <div className="font-mono-code font-bold">v{snap.version_number}</div>
                    <div className="text-[10px] opacity-80">{snap.trigger_event_type}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-12 text-sm text-slate-500">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Reconstructing state...
            </div>
          ) : (
            reconstructed && (
              <div className="space-y-4">
                <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div>
                    <div className="font-mono-code text-xs font-semibold text-[#0f2942]">
                      Mode: {reconstructed.reconstruction_mode}
                    </div>
                    <div className="text-xs text-slate-600">
                      {reconstructed.diff_against_live.length === 0
                        ? "Matches current live state."
                        : `${reconstructed.diff_against_live.length} section(s) differ from current live state.`}
                    </div>
                  </div>
                  {selectedVersion !== null && selectedVersion !== timeline?.current_version && (
                    <button
                      type="button"
                      onClick={handleRestore}
                      disabled={restoring}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-[#0d9488] px-3.5 py-2 text-xs font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
                    >
                      {restoring ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <RotateCcw className="h-3.5 w-3.5" />
                      )}
                      Restore v{selectedVersion}
                    </button>
                  )}
                </div>

                {reconstructed.diff_against_live.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                      Diff Against Current Live State
                    </h4>
                    {reconstructed.diff_against_live.map((d) => (
                      <div
                        key={d.section_id}
                        className="rounded-xl border border-amber-200 bg-amber-50/50 px-3.5 py-2.5 text-xs"
                      >
                        <span className="font-semibold text-slate-900">{d.title}</span>{" "}
                        <span className="font-mono-code text-[11px] text-amber-800">({d.change})</span>
                        {d.content_diff?.changed_fields && d.content_diff.changed_fields.length > 0 && (
                          <div className="mt-1 text-[11px] text-slate-600">
                            Changed fields: {d.content_diff.changed_fields.join(", ")} (Δ{" "}
                            {d.content_diff.word_count_delta} words)
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                <div className="space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                    Reconstructed Content Preview
                  </h4>
                  {reconstructed.reconstructed_state.sections.map((sec, idx) => (
                    <div key={sec.id} className="rounded-xl border border-slate-200 p-4">
                      <div className="text-xs font-bold text-[#0f2942]">
                        {idx + 1}. {sec.title}
                      </div>
                      <p className="mt-1.5 whitespace-pre-wrap text-xs text-slate-600 line-clamp-6">
                        {sec.current_content_text || "(Empty at this snapshot)"}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}
