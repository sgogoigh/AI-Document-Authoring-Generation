"use client";

import {
  ArrowDown,
  ArrowUp,
  Check,
  FileSpreadsheet,
  FileText,
  Image as ImageIcon,
  Loader2,
  Plus,
  Sparkles,
  Trash2,
  Wand2,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { Navbar } from "@/components/ui/Navbar";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { DocType, EditorialTone, OutlineSuggestion, PaletteName } from "@/lib/types";

const DEFAULT_DOCX_SECTIONS = [
  "Executive Summary",
  "Market Landscape & Drivers",
  "Competitive & Strategic Analysis",
  "Recommendations & Next Steps",
];

const DEFAULT_PPTX_SLIDES = [
  "Executive Overview & Thesis",
  "Market Dynamics & Growth Trajectory",
  "Key Operational Metrics",
  "Strategic Roadmap & Action Plan",
];

export default function NewProjectPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [docType, setDocType] = useState<DocType>("docx");
  const [title, setTitle] = useState("");
  const [mainTopic, setMainTopic] = useState("");
  const [palette, setPalette] = useState<PaletteName>("executive_navy");
  const [tone, setTone] = useState<EditorialTone>("executive");
  const [audience, setAudience] = useState("Executive leadership & stakeholders");
  const [includeImages, setIncludeImages] = useState(true);

  const [items, setItems] = useState<string[]>(DEFAULT_DOCX_SECTIONS);
  const [newItemText, setNewItemText] = useState("");

  // Bonus: AI-Suggest Outline state
  const [suggesting, setSuggesting] = useState(false);
  const [suggestion, setSuggestion] = useState<OutlineSuggestion | null>(null);
  const [aiOutlineUsed, setAiOutlineUsed] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
    }
  }, [authLoading, user, router]);

  const handleDocTypeSwitch = (nextType: DocType) => {
    setDocType(nextType);
    setSuggestion(null);
    setAiOutlineUsed(false);
    setItems(nextType === "pptx" ? [...DEFAULT_PPTX_SLIDES] : [...DEFAULT_DOCX_SECTIONS]);
  };

  const handleSlideCountChange = (targetCount: number) => {
    const clamped = Math.max(2, Math.min(15, targetCount));
    setItems((prev) => {
      if (clamped === prev.length) return prev;
      if (clamped < prev.length) return prev.slice(0, clamped);
      const next = [...prev];
      while (next.length < clamped) {
        next.push(`Slide ${next.length + 1}: Key Insights`);
      }
      return next;
    });
  };

  const addItem = () => {
    const clean = newItemText.trim();
    if (!clean) return;
    setItems((prev) => [...prev, clean]);
    setNewItemText("");
  };

  const updateItem = (idx: number, val: string) => {
    setItems((prev) => prev.map((it, i) => (i === idx ? val : it)));
  };

  const removeItem = (idx: number) => {
    if (items.length <= 1) return;
    setItems((prev) => prev.filter((_, i) => i !== idx));
  };

  const moveItem = (idx: number, dir: -1 | 1) => {
    const target = idx + dir;
    if (target < 0 || target >= items.length) return;
    setItems((prev) => {
      const next = [...prev];
      const [moved] = next.splice(idx, 1);
      next.splice(target, 0, moved);
      return next;
    });
  };

  const handleAISuggestOutline = async () => {
    if (mainTopic.trim().length < 3) {
      setError("Enter a main topic or prompt first so Gemini can suggest an outline.");
      return;
    }
    setError(null);
    setSuggesting(true);
    try {
      const res = await api.suggestOutline({
        doc_type: docType,
        main_topic: mainTopic.trim(),
        target_count: docType === "pptx" ? items.length : undefined,
      });
      setSuggestion(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to suggest outline.");
    } finally {
      setSuggesting(false);
    }
  };

  const acceptSuggestedOutline = () => {
    if (!suggestion) return;
    if (!title.trim()) {
      setTitle(suggestion.recommended_title);
    }
    setItems([...suggestion.items]);
    setAiOutlineUsed(true);
    setSuggestion(null);
  };

  const discardSuggestedOutline = () => {
    setSuggestion(null);
  };

  const handleSubmit = async (e: FormEvent, generateImmediately: boolean) => {
    e.preventDefault();
    setError(null);
    const validItems = items.map((s) => s.trim()).filter(Boolean);
    if (mainTopic.trim().length < 3) {
      setError("Please enter a main topic or prompt.");
      return;
    }
    if (validItems.length === 0) {
      setError("Add at least one section header or slide title.");
      return;
    }

    const effectiveTitle = title.trim() || mainTopic.trim().slice(0, 70);
    setSubmitting(true);
    setStatusMessage("Saving project configuration...");

    try {
      const project = await api.createProject({
        title: effectiveTitle,
        doc_type: docType,
        main_topic: mainTopic.trim(),
        theme_config: {
          palette,
          tone,
          audience,
          include_images: includeImages,
        },
        sections: validItems.map((it) => ({ title: it })),
        ai_outline_suggested: aiOutlineUsed,
      });

      if (generateImmediately) {
        setStatusMessage(
          `Generating ${validItems.length} ${docType === "pptx" ? "slides" : "sections"}${
            includeImages ? " and bespoke Gemini visuals" : ""
          }...`
        );
        await api.generateProject(project.id, { generate_images: includeImages });
      }

      router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project.");
      setSubmitting(false);
      setStatusMessage(null);
    }
  };

  return (
    <div className="min-h-screen bg-[#f7f8fa]">
      <Navbar />

      <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="mb-8">
          <p className="text-xs font-semibold uppercase tracking-wider text-teal-700">
            Step 1 — Document Scaffolding
          </p>
          <h1 className="font-editorial text-3xl font-semibold text-[#0f2942] sm:text-4xl">
            Configure New Document
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Choose Word or PowerPoint, define your topic, and customize your outline—or let Gemini suggest one.
          </p>
        </div>

        <form onSubmit={(e) => handleSubmit(e, true)} className="space-y-8">
          {/* 1. Format Picker */}
          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500">
              1. Select Document Format
            </h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => handleDocTypeSwitch("docx")}
                className={`flex items-start gap-4 rounded-xl border-2 p-4 text-left transition ${
                  docType === "docx"
                    ? "border-[#0f2942] bg-[#0f2942]/[0.03]"
                    : "border-slate-200 hover:border-slate-300"
                }`}
              >
                <div className="rounded-xl bg-sky-100 p-2.5 text-sky-700">
                  <FileText className="h-6 w-6" />
                </div>
                <div>
                  <div className="font-semibold text-slate-900">Microsoft Word (.docx)</div>
                  <p className="mt-1 text-xs text-slate-600">
                    Structured business reports with cover page, callout takeaways, tables, and embedded figures.
                  </p>
                </div>
              </button>

              <button
                type="button"
                onClick={() => handleDocTypeSwitch("pptx")}
                className={`flex items-start gap-4 rounded-xl border-2 p-4 text-left transition ${
                  docType === "pptx"
                    ? "border-[#0f2942] bg-[#0f2942]/[0.03]"
                    : "border-slate-200 hover:border-slate-300"
                }`}
              >
                <div className="rounded-xl bg-amber-100 p-2.5 text-amber-700">
                  <FileSpreadsheet className="h-6 w-6" />
                </div>
                <div>
                  <div className="font-semibold text-slate-900">PowerPoint (.pptx)</div>
                  <p className="mt-1 text-xs text-slate-600">
                    16:9 executive slide decks with agenda, KPI cards, visual split layouts, and speaker notes.
                  </p>
                </div>
              </button>
            </div>
          </section>

          {/* 2. Topic & Style */}
          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500">
                2. Main Topic & Editorial Style
              </h2>
              <button
                type="button"
                onClick={handleAISuggestOutline}
                disabled={suggesting}
                className="inline-flex items-center gap-2 rounded-xl border border-teal-300 bg-teal-50 px-4 py-2 text-xs font-semibold text-teal-800 shadow-xs transition hover:bg-teal-100 disabled:opacity-60"
              >
                {suggesting ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Wand2 className="h-3.5 w-3.5" />
                )}
                {suggesting ? "Suggesting Outline..." : "AI-Suggest Outline"}
              </button>
            </div>

            <div>
              <label htmlFor="mainTopic" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-600">
                Main Topic or Prompt *
              </label>
              <textarea
                id="mainTopic"
                rows={3}
                required
                value={mainTopic}
                onChange={(e) => setMainTopic(e.target.value)}
                placeholder="e.g., A market analysis of the EV industry in 2025 covering battery supply chains, charging infrastructure, and regional adoption"
                className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 outline-none transition focus:border-[#0d9488] focus:ring-2 focus:ring-[#0d9488]/20"
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="projectTitle" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Document Title (optional)
                </label>
                <input
                  id="projectTitle"
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Auto-filled from topic or AI suggestion"
                  className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 outline-none focus:border-[#0d9488]"
                />
              </div>

              <div>
                <label htmlFor="audience" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Target Audience
                </label>
                <input
                  id="audience"
                  type="text"
                  value={audience}
                  onChange={(e) => setAudience(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 outline-none focus:border-[#0d9488]"
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <label htmlFor="palette" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Visual Palette
                </label>
                <select
                  id="palette"
                  value={palette}
                  onChange={(e) => setPalette(e.target.value as PaletteName)}
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none focus:border-[#0d9488]"
                >
                  <option value="executive_navy">Executive Navy & Teal</option>
                  <option value="emerald_slate">Emerald & Slate</option>
                  <option value="obsidian_gold">Obsidian & Amber Gold</option>
                  <option value="warm_editorial">Deep Plum & Rose</option>
                </select>
              </div>

              <div>
                <label htmlFor="tone" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-600">
                  Editorial Tone
                </label>
                <select
                  id="tone"
                  value={tone}
                  onChange={(e) => setTone(e.target.value as EditorialTone)}
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none focus:border-[#0d9488]"
                >
                  <option value="executive">Executive</option>
                  <option value="analytical">Analytical</option>
                  <option value="persuasive">Persuasive</option>
                  <option value="technical">Technical</option>
                </select>
              </div>

              <div className="flex items-end">
                <label className="flex w-full cursor-pointer items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5">
                  <span className="inline-flex items-center gap-2 text-xs font-semibold text-slate-700">
                    <ImageIcon className="h-4 w-4 text-teal-700" />
                    Gemini Visuals
                  </span>
                  <input
                    type="checkbox"
                    checked={includeImages}
                    onChange={(e) => setIncludeImages(e.target.checked)}
                    className="h-4 w-4 accent-[#0d9488]"
                  />
                </label>
              </div>
            </div>

            {/* AI-Suggest Outline Preview Banner */}
            {suggestion && (
              <div className="rounded-xl border border-teal-300 bg-teal-50/70 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-teal-800">
                      <Sparkles className="h-3.5 w-3.5" />
                      AI-Suggested Structure
                    </div>
                    <h3 className="mt-1 font-editorial text-lg font-semibold text-[#0f2942]">
                      {suggestion.recommended_title}
                    </h3>
                    <p className="text-xs text-slate-600">{suggestion.rationale}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={acceptSuggestedOutline}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-[#0d9488] px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-700"
                    >
                      <Check className="h-3.5 w-3.5" />
                      Accept Outline
                    </button>
                    <button
                      type="button"
                      onClick={discardSuggestedOutline}
                      className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                    >
                      <X className="h-3.5 w-3.5" />
                      Discard
                    </button>
                  </div>
                </div>
                <ol className="mt-3 grid gap-1.5 sm:grid-cols-2">
                  {suggestion.items.map((item, idx) => (
                    <li key={idx} className="rounded-lg bg-white/90 px-3 py-1.5 text-xs font-medium text-slate-800 border border-teal-200/70">
                      <span className="font-mono-code mr-2 text-teal-700">{idx + 1}.</span>
                      {item}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </section>

          {/* 3. Format-Specific Outline / Slide Builder */}
          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500">
                  {docType === "pptx"
                    ? "3. Slide Count & Slide Titles"
                    : "3. Document Outline (Section Headers)"}
                </h2>
                <p className="mt-0.5 text-xs text-slate-500">
                  {docType === "pptx"
                    ? "Set the number of slides and specify a title/heading for each slide."
                    : "Add, remove, edit, or reorder your Word section headers."}
                </p>
              </div>

              {docType === "pptx" && (
                <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5">
                  <label htmlFor="slideCount" className="text-xs font-semibold text-slate-700">
                    Slides:
                  </label>
                  <input
                    id="slideCount"
                    type="number"
                    min={2}
                    max={15}
                    value={items.length}
                    onChange={(e) => handleSlideCountChange(Number(e.target.value) || 2)}
                    className="w-14 rounded-lg border border-slate-300 bg-white px-2 py-1 text-center text-xs font-semibold"
                  />
                </div>
              )}
            </div>

            <div className="mt-4 space-y-2.5">
              {items.map((item, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <span className="font-mono-code w-16 shrink-0 rounded-lg bg-slate-100 px-2 py-2 text-center text-xs font-semibold text-slate-600">
                    {docType === "pptx" ? `Slide ${idx + 1}` : `Sec ${idx + 1}`}
                  </span>
                  <input
                    type="text"
                    value={item}
                    onChange={(e) => updateItem(idx, e.target.value)}
                    aria-label={`${docType === "pptx" ? "Slide" : "Section"} ${idx + 1} title`}
                    className="flex-1 rounded-xl border border-slate-300 px-3.5 py-2 text-sm text-slate-900 outline-none focus:border-[#0d9488]"
                  />
                  <button
                    type="button"
                    onClick={() => moveItem(idx, -1)}
                    disabled={idx === 0}
                    title="Move up"
                    className="rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-100 disabled:opacity-30"
                  >
                    <ArrowUp className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => moveItem(idx, 1)}
                    disabled={idx === items.length - 1}
                    title="Move down"
                    className="rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-100 disabled:opacity-30"
                  >
                    <ArrowDown className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => removeItem(idx)}
                    disabled={items.length <= 1}
                    title="Remove"
                    className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:bg-rose-50 hover:text-rose-600 disabled:opacity-30"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>

            <div className="mt-4 flex gap-2">
              <input
                type="text"
                value={newItemText}
                onChange={(e) => setNewItemText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addItem();
                  }
                }}
                placeholder={
                  docType === "pptx" ? "Add another slide title..." : "Add another section header..."
                }
                className="flex-1 rounded-xl border border-dashed border-slate-300 bg-slate-50 px-3.5 py-2 text-sm text-slate-900 outline-none focus:border-[#0d9488] focus:bg-white"
              />
              <button
                type="button"
                onClick={addItem}
                className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                <Plus className="h-4 w-4" />
                Add {docType === "pptx" ? "Slide" : "Section"}
              </button>
            </div>
          </section>

          {error && (
            <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {error}
            </div>
          )}

          {statusMessage && (
            <div className="flex items-center gap-3 rounded-xl border border-teal-200 bg-teal-50 px-4 py-3 text-sm font-medium text-teal-900">
              <Loader2 className="h-4 w-4 animate-spin text-teal-700" />
              {statusMessage}
            </div>
          )}

          <div className="flex flex-wrap items-center justify-end gap-3">
            <button
              type="button"
              disabled={submitting}
              onClick={(e) => handleSubmit(e, false)}
              className="rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            >
              Save Draft Only
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center gap-2 rounded-xl bg-[#0f2942] px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-[#173b5e] disabled:opacity-60"
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              Create & Generate Content
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
