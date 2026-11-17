import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import MonitoringPage from "@/app/monitoring/page";
import { api, setStoredTokens } from "@/lib/api";
import { AuthProvider } from "@/lib/auth-context";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/monitoring",
  useSearchParams: () => new URLSearchParams(),
}));

describe("Monitoring, Audit Logs & Reconstruction Console", () => {
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
    vi.spyOn(api, "listProjects").mockResolvedValue([
      {
        id: "p1",
        title: "EV Market 2025",
        doc_type: "docx",
        main_topic: "EV Analysis",
        status: "ready",
        theme_config_json: {
          palette: "executive_navy",
          tone: "executive",
          audience: "Board",
          include_images: true,
        },
        ai_outline_suggested: true,
        current_version: 3,
        section_count: 4,
        like_count: 3,
        dislike_count: 1,
        export_count: 2,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]);
    vi.spyOn(api, "getMonitoringMetrics").mockResolvedValue({
      analytics: {
        llm: {
          total_calls: 6,
          successful_calls: 6,
          failed_calls: 0,
          error_rate: 0,
          total_input_tokens: 1200,
          total_output_tokens: 2400,
          total_tokens: 3600,
          avg_latency_ms: 410,
          p50_latency_ms: 390,
          p95_latency_ms: 680,
          operations_breakdown: {},
        },
        feedback: {
          like_count: 3,
          dislike_count: 1,
          none_count: 0,
          satisfaction_rate_pct: 75,
        },
        exports: { total_exports: 2 },
        audit: { total_events: 12, event_type_counts: {} },
      },
      recent_llm_calls: [
        {
          id: "m1",
          trace_id: "tr-1",
          project_id: "p1",
          section_id: "s1",
          operation: "section_refine",
          provider: "gemini",
          model_name: "gemini-2.5-flash",
          input_tokens: 200,
          output_tokens: 300,
          total_tokens: 500,
          latency_ms: 350,
          status: "success",
          error_message: null,
          prompt_preview: "Refine executive summary",
          created_at: new Date().toISOString(),
        },
      ],
      total_llm_records: 1,
    });
  });

  it("renders analytics, filters audit logs, expands JSON diff, and reconstructs state", async () => {
    const logsSpy = vi.spyOn(api, "getAuditLogs").mockResolvedValue({
      total: 1,
      limit: 50,
      offset: 0,
      items: [
        {
          seq_id: 42,
          event_id: "ev-42",
          trace_id: "trace-abcdef123456",
          user_id: "u1",
          project_id: "p1",
          section_id: "s1",
          event_type: "SECTION_REFINE",
          severity: "INFO",
          entity_type: "section",
          entity_id: "s1",
          http_method: "POST",
          endpoint: "/api/v1/sections/s1/refine",
          status_code: 200,
          duration_ms: 355,
          before_state_json: { revision_number: 1 },
          after_state_json: { revision_number: 2 },
          metadata_json: { refinement_prompt: "Make this more formal" },
          created_at: new Date().toISOString(),
        },
      ],
    });

    const reconSpy = vi.spyOn(api, "reconstructProject").mockResolvedValue({
      project_id: "p1",
      reconstruction_mode: "snapshot_v1",
      reconstructed_state: {
        title: "EV Market 2025",
        doc_type: "docx",
        main_topic: "EV Analysis",
        version_number: 1,
        sections: [
          {
            id: "s1",
            order_index: 0,
            title: "Executive Summary",
            current_content_json: null,
            current_content_text: "Initial v1 content",
            like_status: "none",
            comments: [],
          },
        ],
      },
      diff_against_live: [{ section_id: "s1", title: "Executive Summary", change: "modified" }],
    });

    const user = userEvent.setup();
    render(
      <AuthProvider>
        <MonitoringPage />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByText("75%")).toBeInTheDocument());
    expect(screen.getByText("#42")).toBeInTheDocument();

    // Expand audit row to view before/after JSON
    await user.click(screen.getByText("#42"));
    expect(await screen.findByText(/Before State/i)).toBeInTheDocument();

    // Filter by event type
    await user.selectOptions(screen.getByLabelText("Filter by event type"), "SECTION_REFINE");
    await waitFor(() =>
      expect(logsSpy).toHaveBeenCalledWith(
        expect.objectContaining({ event_type: "SECTION_REFINE" })
      )
    );

    // Reconstruct state
    await user.click(screen.getByRole("button", { name: /Reconstruct State/i }));
    await waitFor(() => expect(reconSpy).toHaveBeenCalledWith("p1", { version: 1 }));
    expect(await screen.findByText("Initial v1 content")).toBeInTheDocument();
  });
});
