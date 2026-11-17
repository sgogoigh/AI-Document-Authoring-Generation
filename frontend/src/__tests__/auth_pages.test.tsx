import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import GoogleCallbackPage from "@/app/auth/google/callback/page";
import LoginPage from "@/app/login/page";
import RegisterPage from "@/app/register/page";
import { GoogleSignInButton } from "@/components/auth/GoogleSignInButton";
import { ApiError, api, clearStoredTokens, getStoredTokens } from "@/lib/api";
import { AuthProvider } from "@/lib/auth-context";

const mockPush = vi.fn();
const mockReplace = vi.fn();
let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
  usePathname: () => "/login",
  useSearchParams: () => mockSearchParams,
}));

describe("Auth pages & Google Sign-In UI", () => {
  beforeEach(() => {
    clearStoredTokens();
    mockPush.mockReset();
    mockReplace.mockReset();
    mockSearchParams = new URLSearchParams();
    vi.restoreAllMocks();
  });

  it("logs in user with email/password and redirects to /dashboard", async () => {
    vi.spyOn(api, "login").mockResolvedValue({
      access_token: "jwt-acc",
      refresh_token: "jwt-ref",
      token_type: "bearer",
      expires_in: 3600,
      user: {
        id: "u1",
        email: "alice@example.com",
        full_name: "Alice",
        auth_provider: "local",
        avatar_url: null,
        is_active: true,
        created_at: new Date().toISOString(),
        last_login_at: null,
      },
    });

    const user = userEvent.setup();
    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    );

    await user.type(screen.getByLabelText(/Email Address/i), "alice@example.com");
    await user.type(screen.getByLabelText(/Password/i), "Password123!");
    await user.click(screen.getByRole("button", { name: /^Sign In$/i }));

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/dashboard"));
    expect(getStoredTokens().accessToken).toBe("jwt-acc");
  });

  it("validates minimum password length on registration", async () => {
    const regSpy = vi.spyOn(api, "register");
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <RegisterPage />
      </AuthProvider>
    );

    await user.type(screen.getByLabelText(/Full Name/i), "Bob");
    await user.type(screen.getByLabelText(/Work Email/i), "bob@example.com");
    await user.type(screen.getByLabelText(/Password/i), "short");
    await user.click(screen.getByRole("button", { name: /Create Account/i }));

    expect(screen.getByRole("alert")).toHaveTextContent("at least 8 characters");
    expect(regSpy).not.toHaveBeenCalled();
  });

  it("shows clear notice when Google OAuth is not configured (503)", async () => {
    vi.spyOn(api, "getGoogleAuthUrl").mockRejectedValue(
      new ApiError(503, "Google OAuth is not configured")
    );
    const user = userEvent.setup();
    render(<GoogleSignInButton />);

    await user.click(screen.getByRole("button", { name: /Continue with Google/i }));
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("GOOGLE_CLIENT_ID")
    );
  });

  it("exchanges Google OAuth code on callback and redirects to /dashboard", async () => {
    mockSearchParams = new URLSearchParams("code=google-auth-code-999");
    vi.spyOn(api, "exchangeGoogleCode").mockResolvedValue({
      access_token: "g-acc",
      refresh_token: "g-ref",
      token_type: "bearer",
      expires_in: 3600,
      user: {
        id: "u-goog",
        email: "goog@example.com",
        full_name: "Google User",
        auth_provider: "google",
        avatar_url: null,
        is_active: true,
        created_at: new Date().toISOString(),
        last_login_at: null,
      },
    });

    render(
      <AuthProvider>
        <GoogleCallbackPage />
      </AuthProvider>
    );

    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/dashboard"));
    expect(getStoredTokens().accessToken).toBe("g-acc");
  });
});
