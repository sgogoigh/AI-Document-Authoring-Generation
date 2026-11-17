import type { Metadata } from "next";

import { AuthProvider } from "@/lib/auth-context";
import "./globals.css";

export const metadata: Metadata = {
  title: "DocCraft AI — Executive Document Authoring & Generation Studio",
  description:
    "Generate, iteratively refine, audit, reconstruct, and export polished Word (.docx) and PowerPoint (.pptx) business documents with Gemini AI.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#f7f8fa] text-slate-900 antialiased">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
