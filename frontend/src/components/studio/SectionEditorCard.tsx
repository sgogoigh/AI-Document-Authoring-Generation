"use client";

import {
  History,
  ImagePlus,
  Loader2,
  MessageSquare,
  Send,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Trash2,
} from "lucide-react";
import { FormEvent, useState } from "react";

import { api } from "@/lib/api";
import type { DocType, DocumentSection, LikeStatus, SectionRevision } from "@/lib/types";
import { AuthenticatedAssetImage } from "./AuthenticatedAssetImage";

const QUICK_REFINEMENT_CHIPS = [
  "Make this more formal",
  "Convert to bullet points",
  "Shorten to 100 words",
  "Add sharper executive takeaways",
];

interface SectionEditorCardProps {
  docType: DocType;
  section: DocumentSection;
  index: number;
  onSectionUpdated: (updated: DocumentSection) => void;
}

export function SectionEditorCard({
  docType,
  section,
  index,
  onSectionUpdated,
}: SectionEditorCardProps) {
  const [prompt, setPrompt] = useState("");
  const [refining, setRefining] = useState(false);
  const [regenImage, setRegenImage] = useState(false);
  const [commentText, setCommentText] = useState("");
  const [savingComment, setSavingComment] = useState(false);
  const [showRevisions, setShowRevisions] = useState(false);
  const [revisions, setRevisions] = useState<SectionRevision[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const content = (section.current_content_json || {}) as Record<string, unknown>;
  const activeAsset = section.assets[section.assets.length - 1];

  const handleRefine = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!prompt.trim()) return;
    setError(null);
    setRefining(true);
    try {
      const updated = await api.refineSection(section.id, {
        refinement_prompt: prompt.trim(),
      });
      onSectionUpdated(updated);
      setPrompt("");
      if (showRevisions) {
        const revs = await api.listRevisions(section.id);
        setRevisions(revs);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Refinement failed.");
    } finally {
      setRefining(false);
    }
  };

  const handleRegenerateImage = async () => {
    setError(null);
    setRegenImage(true);
    try {
      const updated = await api.regenerateSectionImage(section.id);
      onSectionUpdated(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Image generation failed.");
    } finally {
      setRegenImage(false);
    }
  };

  const handleFeedback = async (target: "like" | "dislike") => {
    setError(null);
    const nextRating: LikeStatus = section.like_status === target ? "none" : target;
    try {
      const updated = await api.setFeedback(section.id, nextRating);
      onSectionUpdated(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save feedback.");
    }
  };

  const handleAddComment = async (e: FormEvent) => {
    e.preventDefault();
    if (!commentText.trim()) return;
    setSavingComment(true);
    setError(null);
    try {
      const created = await api.addComment(section.id, commentText.trim());
      onSectionUpdated({
        ...section,
        comments: [...section.comments, created],
      });
      setCommentText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save comment.");
    } finally {
      setSavingComment(false);
    }
  };

  const handleDeleteComment = async (commentId: string) => {
    try {
      await api.deleteComment(commentId);
      onSectionUpdated({
        ...section,
        comments: section.comments.filter((c) => c.id !== commentId),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete comment.");
    }
  };

  const toggleRevisions = async () => {
    const nextOpen = !showRevisions;
    setShowRevisions(nextOpen);
    if (nextOpen && !revisions) {
      try {
        const revs = await api.listRevisions(section.id);
        setRevisions(revs);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not load revisions.");
      }
    }
  };

  const renderStructuredBody = () => {
    if (!section.current_content_json) {
      return (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500">
          No content generated yet for this {docType === "pptx" ? "slide" : "section"}. Use{" "}
          <strong>Generate Content</strong> in the top bar.
        </div>
      );
    }

    if (docType === "pptx") {
      const kicker = typeof content.kicker === "string" ? content.kicker : "";
      const subtitle = typeof content.subtitle === "string" ? content.subtitle : "";
      const bullets = Array.isArray(content.bullets) ? (content.bullets as string[]) : [];
      const secondaryBullets = Array.isArray(content.secondary_bullets)
        ? (content.secondary_bullets as string[])
        : [];
      const secondaryTitle =
        typeof content.secondary_column_title === "string" ? content.secondary_column_title : "";
      const metricCards = Array.isArray(content.metric_cards)
        ? (content.metric_cards as Array<{ value: string; label: string }>)
        : [];
      const speakerNotes = typeof content.speaker_notes === "string" ? content.speaker_notes : "";

      return (
        <div className="space-y-4">
          {/* Slide Preview Surface */}
          <div className="rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-5">
            {kicker && (
              <div className="text-[11px] font-bold uppercase tracking-wider text-teal-700">
                {kicker}
              </div>
            )}
            {subtitle && <p className="mt-1 text-sm font-medium text-slate-600">{subtitle}</p>}

            {metricCards.length > 0 && (
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                {metricCards.map((mc, i) => (
                  <div key={i} className="rounded-xl border border-teal-200/80 bg-teal-50/50 p-3">
                    <div className="text-xl font-bold text-[#0f2942]">{mc.value}</div>
                    <div className="text-xs text-slate-600">{mc.label}</div>
                  </div>
                ))}
              </div>
            )}

            <div className={`mt-4 grid gap-5 ${activeAsset || secondaryBullets.length > 0 ? "lg:grid-cols-2" : ""}`}>
              <ul className="space-y-2.5">
                {bullets.map((b, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-800">
                    <span className="mt-1 text-teal-600">▸</span>
                    <span>{b}</span>
                  </li>
                ))}
              </ul>

              {secondaryBullets.length > 0 && (
                <div className="rounded-xl border border-slate-200 bg-white p-4">
                  <div className="mb-2 text-xs font-bold uppercase tracking-wider text-[#0f2942]">
                    {secondaryTitle || "Strategic Implications"}
                  </div>
                  <ul className="space-y-2">
                    {secondaryBullets.map((b, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                        <span className="mt-1 text-teal-600">▸</span>
                        <span>{b}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {activeAsset && (
                <AuthenticatedAssetImage assetId={activeAsset.id} caption={activeAsset.caption} />
              )}
            </div>
          </div>

          {speakerNotes && (
            <div className="rounded-xl border border-amber-200/80 bg-amber-50/50 px-4 py-3 text-xs text-slate-700">
              <span className="font-semibold uppercase tracking-wider text-amber-800">
                Speaker Notes:{" "}
              </span>
              {speakerNotes}
            </div>
          )}
        </div>
      );
    }

    // DOCX structured preview
    const summaryCallout = typeof content.summary_callout === "string" ? content.summary_callout : "";
    const paragraphs = Array.isArray(content.paragraphs) ? (content.paragraphs as string[]) : [];
    const bulletPoints = Array.isArray(content.bullet_points)
      ? (content.bullet_points as Array<{ label?: string; detail?: string } | string>)
      : [];
    const dataTable = content.data_table as
      | { title?: string; headers?: string[]; rows?: string[][] }
      | null
      | undefined;

    return (
      <div className="space-y-4">
        {summaryCallout && (
          <div className="rounded-r-xl border-l-4 border-[#0d9488] bg-teal-50/70 px-4 py-3 text-sm text-[#0f2942]">
            <span className="mr-1.5 text-xs font-bold uppercase tracking-wider text-teal-700">
              Key Takeaway:
            </span>
            <span className="italic">{summaryCallout}</span>
          </div>
        )}

        <div className="space-y-3 text-sm leading-relaxed text-slate-700">
          {paragraphs.map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>

        {bulletPoints.length > 0 && (
          <ul className="space-y-2 pl-1">
            {bulletPoints.map((bp, i) => (
              <li key={i} className="flex items-start gap-2.5 text-sm text-slate-700">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#0d9488]" />
                <span>
                  {typeof bp === "string" ? (
                    bp
                  ) : (
                    <>
                      {bp.label && <strong className="text-[#0f2942]">{bp.label}: </strong>}
                      {bp.detail}
                    </>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}

        {dataTable && dataTable.headers && dataTable.rows && (
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            {dataTable.title && (
              <div className="bg-slate-50 px-4 py-2 text-xs font-semibold text-[#0f2942] border-b border-slate-200">
                {dataTable.title}
              </div>
            )}
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-[#0f2942] text-white">
                <tr>
                  {dataTable.headers.map((h, i) => (
                    <th key={i} className="px-3.5 py-2.5 font-semibold">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {dataTable.rows.map((row, rIdx) => (
                  <tr key={rIdx} className={rIdx % 2 === 1 ? "bg-slate-50/70" : ""}>
                    {row.map((cell, cIdx) => (
                      <td key={cIdx} className="px-3.5 py-2 text-slate-700">
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeAsset && (
          <AuthenticatedAssetImage assetId={activeAsset.id} caption={activeAsset.caption} />
        )}
      </div>
    );
  };

  return (
    <article
      id={`section-${section.id}`}
      className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs"
    >
      {/* Section Header + Feedback Controls */}
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono-code rounded-md bg-[#0f2942] px-2 py-0.5 text-xs font-semibold text-white">
              {docType === "pptx" ? `Slide ${index + 1}` : `Section ${index + 1}`}
            </span>
            <span className="font-mono-code rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
              {section.revision_count} rev{section.revision_count === 1 ? "" : "s"}
            </span>
          </div>
          <h2 className="mt-2 font-editorial text-2xl font-semibold text-[#0f2942]">
            {section.title}
          </h2>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => handleFeedback("like")}
            aria-label={`Like ${section.title}`}
            aria-pressed={section.like_status === "like"}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold transition ${
              section.like_status === "like"
                ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            <ThumbsUp className="h-3.5 w-3.5" />
            Like
          </button>

          <button
            type="button"
            onClick={() => handleFeedback("dislike")}
            aria-label={`Dislike ${section.title}`}
            aria-pressed={section.like_status === "dislike"}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold transition ${
              section.like_status === "dislike"
                ? "border-rose-300 bg-rose-50 text-rose-700"
                : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            <ThumbsDown className="h-3.5 w-3.5" />
            Dislike
          </button>

          <button
            type="button"
            onClick={toggleRevisions}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
          >
            <History className="h-3.5 w-3.5" />
            Revisions
          </button>
        </div>
      </div>

      {/* Rendered Content */}
      <div className="mt-5">{renderStructuredBody()}</div>

      {/* Section Revision History Drawer */}
      {showRevisions && (
        <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-600">
            Section Revision Log
          </div>
          {!revisions ? (
            <div className="text-xs text-slate-500">Loading revisions...</div>
          ) : revisions.length === 0 ? (
            <div className="text-xs text-slate-500">No revisions recorded yet.</div>
          ) : (
            <div className="space-y-2">
              {revisions.map((rev) => (
                <div
                  key={rev.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs"
                >
                  <div>
                    <span className="font-mono-code font-semibold text-[#0f2942]">
                      r{rev.revision_number}
                    </span>{" "}
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-slate-600">
                      {rev.source}
                    </span>
                    {rev.refinement_prompt && (
                      <span className="ml-2 italic text-slate-600">“{rev.refinement_prompt}”</span>
                    )}
                  </div>
                  <div className="font-mono-code text-[11px] text-slate-500">
                    v{rev.project_version} • Δ{" "}
                    {rev.diff_summary_json?.word_count_delta !== undefined
                      ? `${rev.diff_summary_json.word_count_delta >= 0 ? "+" : ""}${
                          rev.diff_summary_json.word_count_delta
                        } words`
                      : "0"}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* AI Refinement Prompt + Visual Regeneration */}
      {section.current_content_json && (
        <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50/70 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label
              htmlFor={`refine-${section.id}`}
              className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#0f2942]"
            >
              <Sparkles className="h-3.5 w-3.5 text-teal-600" />
              AI Refinement Prompt
            </label>
            <button
              type="button"
              onClick={handleRegenerateImage}
              disabled={regenImage}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100 disabled:opacity-60"
            >
              {regenImage ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <ImagePlus className="h-3 w-3 text-teal-700" />
              )}
              {activeAsset ? "Regenerate Visual" : "Generate Visual"}
            </button>
          </div>

          <div className="mt-2 flex flex-wrap gap-1.5">
            {QUICK_REFINEMENT_CHIPS.map((chip) => (
              <button
                key={chip}
                type="button"
                onClick={() => setPrompt(chip)}
                className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600 hover:border-teal-300 hover:text-teal-800"
              >
                {chip}
              </button>
            ))}
          </div>

          <form onSubmit={handleRefine} className="mt-3 flex gap-2">
            <input
              id={`refine-${section.id}`}
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g., Make this more formal, convert to bullet points, or shorten to 100 words..."
              className="flex-1 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-sm text-slate-900 outline-none focus:border-[#0d9488]"
            />
            <button
              type="submit"
              disabled={refining || !prompt.trim()}
              className="inline-flex items-center gap-1.5 rounded-xl bg-[#0f2942] px-4 py-2 text-xs font-semibold text-white transition hover:bg-[#173b5e] disabled:opacity-50"
            >
              {refining ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
              {refining ? "Refining..." : "Refine"}
            </button>
          </form>
        </div>
      )}

      {/* User Comments Section */}
      <div className="mt-5 border-t border-slate-100 pt-4">
        <div className="mb-2.5 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-500">
          <MessageSquare className="h-3.5 w-3.5" />
          Review Comments ({section.comments.length})
        </div>

        {section.comments.length > 0 && (
          <div className="mb-3 space-y-2">
            {section.comments.map((comment) => (
              <div
                key={comment.id}
                className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-xs text-slate-700"
              >
                <p className="leading-relaxed">{comment.body}</p>
                <button
                  type="button"
                  onClick={() => handleDeleteComment(comment.id)}
                  title="Delete comment"
                  className="text-slate-400 hover:text-rose-600"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}

        <form onSubmit={handleAddComment} className="flex gap-2">
          <input
            type="text"
            aria-label={`Comment on ${section.title}`}
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            placeholder="Add a review note or reminder..."
            className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2 text-xs text-slate-900 outline-none focus:border-[#0d9488] focus:bg-white"
          />
          <button
            type="submit"
            disabled={savingComment || !commentText.trim()}
            className="inline-flex items-center gap-1 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            <Send className="h-3 w-3" />
            Add Note
          </button>
        </form>
      </div>

      {error && (
        <div role="alert" className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {error}
        </div>
      )}
    </article>
  );
}
