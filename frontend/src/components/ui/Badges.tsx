import { FileSpreadsheet, FileText } from "lucide-react";

export function DocTypeBadge({ docType }: { docType: "docx" | "pptx" }) {
  if (docType === "pptx") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-800">
        <FileSpreadsheet className="h-3 w-3" />
        PowerPoint (.pptx)
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-sky-200 bg-sky-50 px-2.5 py-0.5 text-xs font-semibold text-sky-800">
      <FileText className="h-3 w-3" />
      Word (.docx)
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    ready: "border-emerald-200 bg-emerald-50 text-emerald-800",
    configured: "border-indigo-200 bg-indigo-50 text-indigo-800",
    generating: "border-teal-200 bg-teal-50 text-teal-800 animate-pulse",
    draft: "border-slate-200 bg-slate-100 text-slate-700",
    error: "border-rose-200 bg-rose-50 text-rose-800",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize ${
        styles[status] || styles.draft
      }`}
    >
      {status}
    </span>
  );
}
