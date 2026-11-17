import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProjectStudioPage from "@/app/projects/[id]/page";
import { api, setStoredTokens } from "@/lib/api";
import { AuthProvider } from "@/lib/auth-context";
import type { ProjectDetail } from "@/lib/types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/projects/p1",
  useParams: () => ({ id: "p1" }),
}));

const MOCK_PROJECT: ProjectDetail = {
  id: "p1",
  user_id: "u1",
  title: "EV Market 2025",
  doc_type: "docx",
  main_topic: "EV Industry Analysis",
  status: "ready",
  theme_config_json: {
    palette: "executive_navy",
    tone: "executive",
    audience: "Board",
    include_images: true,
  },
  ai_outline_suggested: true,
  current_version: 2,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  sections: [
    {
      id: "sec1",
      project_id: "p1",
      order_index: 0,
      title: "Executive Summary",
      section_kind: "section",
      current_revision_id: "rev1",
      current_content_json: {
        summary_callout: "Initial EV summary callout.",
        paragraphs: ["Initial EV market paragraph."],
        bullet_points: [{ label: "Growth", detail: "28% YoY expansion." }],
      },
      current_content_text: "Initial EV market paragraph.",
      like_status: "none",
      revision_count: 1,
      comments: [],
      assets: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ],
};

describe("Interactive Refinement Studio", () => {
  beforeEach(() => {
    setStoredTokens("acc", "ref");
    vi.restoreAllMocks();
    vi.spyOn(api, "me").mockResolvedValue({
      id: "u1",
      email: "alice@example.com",
      full_name: "Alice",
      auth_provider: "local",
      avatar_url: null,
      is_active: true,
      created_at: new Date().toISOString(),
      last_login_at: null,
    });
    vi.spyOn(api, "getProject").mockResolvedValue(MOCK_PROJECT);
  });

  it("refines a section, toggles like feedback, adds comment, and exports", async () => {
    const refineSpy = vi.spyOn(api, "refineSection").mockResolvedValue({
      ...MOCK_PROJECT.sections[0],
      current_content_json: {
        summary_callout: "Refined concise executive takeaway.",
        paragraphs: ["Refined formal prose."],
        bullet_points: [],
      },
      revision_count: 2,
    });

    const fbSpy = vi.spyOn(api, "setFeedback").mockResolvedValue({
      ...MOCK_PROJECT.sections[0],
      like_status: "like",
    });

    const commentSpy = vi.spyOn(api, "addComment").mockResolvedValue({
      id: "c1",
      section_id: "sec1",
      user_id: "u1",
      body: "Verify battery figure",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    const exportSpy = vi.spyOn(api, "downloadExport").mockResolvedValue({
      blob: new Blob(["docx-bytes"]),
      filename: "EV_Market_2025.docx",
    });
    URL.createObjectURL = vi.fn(() => "blob:test");
    URL.revokeObjectURL = vi.fn();

    const user = userEvent.setup();
    render(
      <AuthProvider>
        <ProjectStudioPage />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByText("Initial EV market paragraph.")).toBeInTheDocument());

    // Refine via prompt
    await user.type(screen.getByLabelText(/AI Refinement Prompt/i), "Make this more formal");
    await user.click(screen.getByRole("button", { name: /^Refine$/i }));
    await waitFor(() => expect(refineSpy).toHaveBeenCalledWith("sec1", { refinement_prompt: "Make this more formal" }));
    expect(await screen.findByText("Refined formal prose.")).toBeInTheDocument();

    // Like button
    await user.click(screen.getByRole("button", { name: /^Like Executive Summary$/i }));
    await waitFor(() => expect(fbSpy).toHaveBeenCalledWith("sec1", "like"));

    // Comment box
    await user.type(screen.getByLabelText(/Comment on Executive Summary/i), "Verify battery figure");
    await user.click(screen.getByRole("button", { name: /Add Note/i }));
    await waitFor(() => expect(commentSpy).toHaveBeenCalledWith("sec1", "Verify battery figure"));
    expect(await screen.findByText("Verify battery figure")).toBeInTheDocument();

    // Export button
    await user.click(screen.getByRole("button", { name: /Export \.docx/i }));
    await waitFor(() => expect(exportSpy).toHaveBeenCalledWith("p1"));
  });
});
