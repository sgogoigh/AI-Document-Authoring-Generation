import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "@/app/dashboard/page";
import NewProjectPage from "@/app/projects/new/page";
import { api, setStoredTokens } from "@/lib/api";
import { AuthProvider } from "@/lib/auth-context";

const mockPush = vi.fn();
const mockReplace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
  usePathname: () => "/dashboard",
}));

const MOCK_USER = {
  id: "u1",
  email: "alice@example.com",
  full_name: "Alice",
  auth_provider: "local" as const,
  avatar_url: null,
  is_active: true,
  created_at: new Date().toISOString(),
  last_login_at: null,
};

describe("Dashboard and Document Configurator", () => {
  beforeEach(() => {
    setStoredTokens("acc", "ref");
    mockPush.mockReset();
    mockReplace.mockReset();
    vi.restoreAllMocks();
    vi.spyOn(api, "me").mockResolvedValue(MOCK_USER);
  });

  it("renders dashboard projects and supports format filtering", async () => {
    const listSpy = vi.spyOn(api, "listProjects").mockResolvedValue([
      {
        id: "p1",
        title: "EV Industry 2025",
        doc_type: "docx",
        main_topic: "EV market outlook",
        status: "ready",
        theme_config_json: {
          palette: "executive_navy",
          tone: "executive",
          audience: "Board",
          include_images: true,
        },
        ai_outline_suggested: true,
        current_version: 2,
        section_count: 5,
        like_count: 4,
        dislike_count: 0,
        export_count: 1,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]);

    const user = userEvent.setup();
    render(
      <AuthProvider>
        <DashboardPage />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByText("EV Industry 2025")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "PowerPoint (.pptx)" }));
    await waitFor(() => expect(listSpy).toHaveBeenCalledWith({ doc_type: "pptx", search: undefined }));
  });

  it("configures pptx slide count and runs AI-Suggest Outline accept workflow", async () => {
    vi.spyOn(api, "suggestOutline").mockResolvedValue({
      recommended_title: "AI Strategy 2026 Deck",
      rationale: "Executive structure from vision to ROI.",
      items: ["Vision & Mandate", "Use Case Portfolio", "Architecture & Governance", "ROI Forecast"],
    });
    const createSpy = vi.spyOn(api, "createProject").mockResolvedValue({
      id: "proj-new",
      user_id: "u1",
      title: "AI Strategy 2026 Deck",
      doc_type: "pptx",
      main_topic: "Enterprise AI Strategy 2026",
      status: "configured",
      theme_config_json: {
        palette: "executive_navy",
        tone: "executive",
        audience: "Executive leadership & stakeholders",
        include_images: true,
      },
      ai_outline_suggested: true,
      current_version: 1,
      sections: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    const genSpy = vi.spyOn(api, "generateProject").mockResolvedValue({} as never);

    const user = userEvent.setup();
    render(
      <AuthProvider>
        <NewProjectPage />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByText("Configure New Document")).toBeInTheDocument());

    await user.click(screen.getByText("PowerPoint (.pptx)"));
    await user.type(screen.getByLabelText(/Main Topic or Prompt/i), "Enterprise AI Strategy 2026");

    await user.click(screen.getByRole("button", { name: /AI-Suggest Outline/i }));
    await waitFor(() => expect(screen.getByText("AI Strategy 2026 Deck")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /Accept Outline/i }));
    expect(screen.getByDisplayValue("Vision & Mandate")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Create & Generate Content/i }));
    await waitFor(() => expect(createSpy).toHaveBeenCalled());
    expect(genSpy).toHaveBeenCalledWith("proj-new", { generate_images: true });
    expect(mockPush).toHaveBeenCalledWith("/projects/proj-new");
  });
});
