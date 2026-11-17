"use client";

import {
  ArrowRight,
  CheckCircle2,
  FileSpreadsheet,
  FileText,
  History,
  Image as ImageIcon,
  ShieldCheck,
  Sparkles,
  Wand2,
} from "lucide-react";
import Link from "next/link";

import { Navbar } from "@/components/ui/Navbar";
import { useAuth } from "@/lib/auth-context";

export default function HomePage() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-[#f7f8fa]">
      <Navbar />

      <main>
        {/* Hero Section */}
        <section className="relative overflow-hidden border-b border-slate-200/80 bg-white">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,_rgba(13,148,136,0.09),_transparent_45%),radial-gradient(circle_at_bottom_left,_rgba(15,41,66,0.06),_transparent_40%)]" />
          <div className="relative mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-24 lg:px-8">
            <div className="grid items-center gap-12 lg:grid-cols-12">
              <div className="lg:col-span-7">
                <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-teal-200 bg-teal-50/80 px-3.5 py-1 text-xs font-semibold text-teal-800">
                  <Sparkles className="h-3.5 w-3.5 text-teal-600" />
                  AI-Assisted Document Authoring & Generation Platform
                </div>
                <h1 className="font-editorial text-4xl font-semibold tracking-tight text-[#0f2942] sm:text-5xl lg:text-6xl leading-[1.08]">
                  Author executive reports and decks with precision.
                </h1>
                <p className="mt-5 max-w-2xl text-lg leading-relaxed text-slate-600">
                  Configure your Word (<code className="font-mono-code text-sm text-[#0f2942]">.docx</code>) or PowerPoint (
                  <code className="font-mono-code text-sm text-[#0f2942]">.pptx</code>) structure, generate
                  context-aware sections and custom visuals with Gemini, refine every block iteratively, and export
                  publication-ready files.
                </p>

                <div className="mt-8 flex flex-wrap items-center gap-4">
                  <Link
                    href={user ? "/projects/new" : "/register"}
                    className="inline-flex items-center gap-2 rounded-xl bg-[#0f2942] px-6 py-3.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#173b5e]"
                  >
                    {user ? "Create New Document" : "Start Authoring Free"}
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                  <Link
                    href={user ? "/dashboard" : "/login"}
                    className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-6 py-3.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                  >
                    {user ? "Open Dashboard" : "Sign In"}
                  </Link>
                </div>

                <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs font-medium text-slate-500">
                  <span className="inline-flex items-center gap-1.5">
                    <CheckCircle2 className="h-4 w-4 text-teal-600" />
                    Section-by-section Gemini generation
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <CheckCircle2 className="h-4 w-4 text-teal-600" />
                    Bespoke AI-generated diagrams
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <CheckCircle2 className="h-4 w-4 text-teal-600" />
                    Full audit log & version reconstruction
                  </span>
                </div>
              </div>

              {/* Editorial Preview Card */}
              <div className="lg:col-span-5">
                <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-200/60">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                    <div>
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-teal-700">
                        Workflow Pipeline
                      </span>
                      <h2 className="font-editorial text-xl font-semibold text-[#0f2942]">
                        EV Industry Market Analysis 2025
                      </h2>
                    </div>
                    <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 border border-emerald-200">
                      Ready • v4
                    </span>
                  </div>

                  <div className="mt-4 space-y-3">
                    {[
                      { step: "01", label: "Configure & AI-Suggest Outline", desc: "5 structured sections or 16:9 slide deck" },
                      { step: "02", label: "Generate Prose, Tables & Visuals", desc: "Context-aware Gemini text + PNG graphics" },
                      { step: "03", label: "Refine, Rate & Comment", desc: "Per-section prompts, Like/Dislike, notes" },
                      { step: "04", label: "Reconstruct & Export", desc: "Point-in-time snapshots + .docx / .pptx" },
                    ].map((item) => (
                      <div
                        key={item.step}
                        className="flex items-start gap-3 rounded-xl border border-slate-100 bg-slate-50/70 p-3"
                      >
                        <span className="font-mono-code rounded-lg bg-[#0f2942] px-2 py-1 text-xs font-semibold text-white">
                          {item.step}
                        </span>
                        <div>
                          <div className="text-sm font-semibold text-slate-800">{item.label}</div>
                          <div className="text-xs text-slate-500">{item.desc}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Feature Grid */}
        <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
          <div className="mb-10 max-w-2xl">
            <h2 className="font-editorial text-3xl font-semibold text-[#0f2942]">
              Built for structured quality and complete traceability
            </h2>
            <p className="mt-2 text-slate-600">
              Every outline change, AI refinement, feedback signal, and export is persisted and reconstructible.
            </p>
          </div>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {[
              {
                icon: FileText,
                title: "Polished Word Reports (.docx)",
                desc: "Cover pages, executive callouts, structured tables, bold-lead bullets, headers, and page numbers.",
              },
              {
                icon: FileSpreadsheet,
                title: "Executive Decks (.pptx)",
                desc: "16:9 widescreen slides with agenda roadmap, KPI cards, two-column comparisons, and speaker notes.",
              },
              {
                icon: Wand2,
                title: "AI-Suggest Outline (Bonus)",
                desc: "Enter a topic and let Gemini propose tailored section headers or slide titles you can edit or accept.",
              },
              {
                icon: ImageIcon,
                title: "Gemini Visual Generation",
                desc: "Generates bespoke editorial illustrations embedded cleanly inside both Word figures and slide frames.",
              },
              {
                icon: History,
                title: "Revision & Reconstruction",
                desc: "Inspect field-level diffs, jump back to any project version or timestamp, and restore non-destructively.",
              },
              {
                icon: ShieldCheck,
                title: "Monitoring & Google Auth",
                desc: "JWT & Google OAuth authentication, filterable audit streams, and real-time LLM token & latency telemetry.",
              },
            ].map((feat) => {
              const Icon = feat.icon;
              return (
                <div
                  key={feat.title}
                  className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs transition hover:border-teal-200 hover:shadow-md"
                >
                  <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-[#0f2942]/5 text-[#0f2942]">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="text-base font-semibold text-slate-900">{feat.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600">{feat.desc}</p>
                </div>
              );
            })}
          </div>
        </section>
      </main>
    </div>
  );
}
