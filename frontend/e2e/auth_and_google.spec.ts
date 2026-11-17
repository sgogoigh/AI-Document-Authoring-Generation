import { expect, test } from "@playwright/test";

test.describe("Authentication & Google Sign-In Flows", () => {
  test("registers a user, logs out, and logs back in via email/password", async ({ page }) => {
    const uniqueEmail = `e2e_${Date.now()}@example.com`;

    await page.goto("/register");
    await page.getByLabel(/Full Name/i).fill("E2E Tester");
    await page.getByLabel(/Work Email/i).fill(uniqueEmail);
    await page.getByLabel(/Password/i).fill("StrongPass123!");
    await page.getByRole("button", { name: /Create Account/i }).click();

    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByText("Your Document Projects")).toBeVisible();
    await expect(page.getByText(uniqueEmail)).toBeVisible();

    await page.getByRole("button", { name: /Sign Out/i }).click();
    await expect(page).toHaveURL(/\/login/);

    await page.getByLabel(/Email Address/i).fill(uniqueEmail);
    await page.getByLabel(/Password/i).fill("StrongPass123!");
    await page.getByRole("button", { name: /^Sign In$/i }).click();

    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByText(uniqueEmail)).toBeVisible();
  });

  test("handles Google Sign-In button and OAuth callback session establishment", async ({
    page,
  }) => {
    await page.goto("/login");
    const googleBtn = page.getByRole("button", { name: /Continue with Google/i });
    await expect(googleBtn).toBeVisible();
    await googleBtn.click();

    // When GOOGLE_CLIENT_ID is empty in local dev, displays clear configuration notice
    await expect(page.getByRole("status")).toContainText("GOOGLE_CLIENT_ID");

    // Verify full Google OAuth callback browser flow establishes session and lands on dashboard
    await page.route("**/api/v1/auth/google/callback", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: "e2e-google-jwt",
          refresh_token: "e2e-google-refresh",
          token_type: "bearer",
          expires_in: 3600,
          user: {
            id: "u-google-e2e",
            email: "google.e2e@example.com",
            full_name: "Google E2E User",
            auth_provider: "google",
            avatar_url: null,
            is_active: true,
            created_at: new Date().toISOString(),
            last_login_at: new Date().toISOString(),
          },
        }),
      });
    });
    await page.route("**/api/v1/auth/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "u-google-e2e",
          email: "google.e2e@example.com",
          full_name: "Google E2E User",
          auth_provider: "google",
          avatar_url: null,
          is_active: true,
          created_at: new Date().toISOString(),
          last_login_at: new Date().toISOString(),
        }),
      });
    });
    await page.route("**/api/v1/projects*", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    });

    await page.goto("/auth/google/callback?code=google-test-code-xyz");
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByText("google.e2e@example.com")).toBeVisible();
  });
});
