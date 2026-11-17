import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

test.describe("Live End-to-End Document Authoring Workflows", () => {
  test("Word (.docx) full flow: AI-Suggest Outline, Generate, Refine, Feedback, Comment, Reconstruct, Export, Monitoring", async ({
    page,
  }, testInfo) => {
    const email = `e2e_docx_${Date.now()}@example.com`;
    await page.goto("/register");
    await page.getByLabel(/Full Name/i).fill("Docx E2E Lead");
    await page.getByLabel(/Work Email/i).fill(email);
    await page.getByLabel(/Password/i).fill("Password123!");
    await page.getByRole("button", { name: /Create Account/i }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    // Configure Word Document + Bonus AI-Suggest Outline
    await page.getByRole("link", { name: /New Document Project/i }).click();
    await expect(page).toHaveURL(/\/projects\/new/);

    await page
      .getByLabel(/Main Topic or Prompt/i)
      .fill("A market analysis of the EV industry in 2025 covering battery supply and charging networks");

    await page.getByRole("button", { name: /AI-Suggest Outline/i }).click();
    await expect(page.getByText("AI-Suggested Structure")).toBeVisible({ timeout: 45_000 });
    await page.getByRole("button", { name: /Accept Outline/i }).click();

    // Limit to 3 sections to keep E2E fast while still testing multi-section generation & images
    const removeBtns = page.getByTitle("Remove");
    while ((await removeBtns.count()) > 3) {
      await removeBtns.last().click();
    }

    await page.getByRole("button", { name: /Create & Generate Content/i }).click();
    await expect(page).toHaveURL(/\/projects\/[a-f0-9-]+/, { timeout: 120_000 });

    // Verify studio rendered
    await expect(page.getByRole("button", { name: /Export \.docx/i })).toBeVisible();
    await expect(page.getByText("Key Takeaway:")).not.toHaveCount(0);

    // Refine Section 1
    const firstRefineInput = page.locator('input[id^="refine-"]').first();
    await firstRefineInput.fill("Shorten into concise formal executive prose under 90 words.");
    await page.getByRole("button", { name: /^Refine$/i }).first().click();
    await expect(page.getByText("2 revs").first()).toBeVisible({ timeout: 45_000 });

    // Like Section 1 & Dislike Section 2
    await page.locator('button[aria-label^="Like "]').first().click();
    await page.locator('button[aria-label^="Dislike "]').nth(1).click();

    // Add comment on Section 1
    const firstCommentInput = page.locator('input[aria-label^="Comment on "]').first();
    await firstCommentInput.fill("Verified EV market metrics for board review.");
    await page.getByRole("button", { name: /Add Note/i }).first().click();
    await expect(page.getByText("Verified EV market metrics for board review.")).toBeVisible();

    // Inspect History & Reconstruction Drawer
    await page.getByRole("button", { name: /History & Reconstruct/i }).click();
    await expect(page.getByText("Project History & Reconstruction")).toBeVisible();
    await expect(page.getByText(/Mode:/)).toBeVisible();
    // Close drawer
    await page.locator("div.fixed button").first().click();

    // Export .docx and verify real downloaded file
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: /Export \.docx/i }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.docx$/);
    const exportPath = path.join(testInfo.outputDir, download.suggestedFilename());
    await download.saveAs(exportPath);
    const stat = fs.statSync(exportPath);
    expect(stat.size).toBeGreaterThan(5000);

    // Verify Monitoring & Audit Log Explorer
    await page.getByRole("link", { name: "Logs", exact: true }).click();
    await expect(page).toHaveURL(/\/monitoring/);
    await expect(page.getByText("Database Monitoring, Telemetry & Reconstruction")).toBeVisible();
    await expect(page.getByRole("cell", { name: "SECTION_REFINE" }).first()).toBeVisible();

    await page.getByRole("button", { name: /Reconstruct State/i }).click();
    await expect(page.getByText(/snapshot_v1|replay_v1/i)).toBeVisible();
  });

  test("PowerPoint (.pptx) full flow: Slide config, Generate, Refine, Feedback, Export", async ({
    page,
  }, testInfo) => {
    const email = `e2e_pptx_${Date.now()}@example.com`;
    await page.goto("/register");
    await page.getByLabel(/Full Name/i).fill("Pptx E2E Lead");
    await page.getByLabel(/Work Email/i).fill(email);
    await page.getByLabel(/Password/i).fill("Password123!");
    await page.getByRole("button", { name: /Create Account/i }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    await page.getByRole("link", { name: /New Document Project/i }).click();
    await page.getByText("PowerPoint (.pptx)").click();
    await page
      .getByLabel(/Main Topic or Prompt/i)
      .fill("Enterprise AI Transformation Roadmap 2026 for Fortune 500 Operations");
    await page.getByLabel(/Document Title/i).fill("Enterprise AI Roadmap 2026");

    await page.getByLabel(/Slides:/i).fill("3");
    await page.getByRole("button", { name: /Create & Generate Content/i }).click();
    await expect(page).toHaveURL(/\/projects\/[a-f0-9-]+/, { timeout: 120_000 });

    await expect(page.getByRole("button", { name: /Export \.pptx/i })).toBeVisible();
    await expect(page.getByText("Speaker Notes:")).not.toHaveCount(0);

    // Refine slide 1
    await page.locator('input[id^="refine-"]').first().fill("Sharpen bullets with concrete KPI focus.");
    await page.getByRole("button", { name: /^Refine$/i }).first().click();
    await expect(page.getByText("2 revs").first()).toBeVisible({ timeout: 45_000 });

    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: /Export \.pptx/i }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.pptx$/);
    const exportPath = path.join(testInfo.outputDir, download.suggestedFilename());
    await download.saveAs(exportPath);
    const stat = fs.statSync(exportPath);
    expect(stat.size).toBeGreaterThan(8000);
  });
});
