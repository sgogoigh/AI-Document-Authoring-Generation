import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api, clearStoredTokens, getStoredTokens, setStoredTokens } from "@/lib/api";
import { AuthProvider, useAuth } from "@/lib/auth-context";

function AuthConsumer() {
  const { user, loading, loginWithSession, logout } = useAuth();
  if (loading) return <div>Loading...</div>;
  return (
    <div>
      <span data-testid="user-email">{user ? user.email : "anonymous"}</span>
      <button
        onClick={() =>
          loginWithSession({
            access_token: "acc-123",
            refresh_token: "ref-123",
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
          })
        }
      >
        Sign In
      </button>
      <button onClick={logout}>Sign Out</button>
    </div>
  );
}

describe("API client and AuthContext", () => {
  beforeEach(() => {
    clearStoredTokens();
    vi.restoreAllMocks();
  });

  it("stores and clears tokens cleanly", () => {
    setStoredTokens("a1", "r1");
    expect(getStoredTokens()).toEqual({ accessToken: "a1", refreshToken: "r1" });
    clearStoredTokens();
    expect(getStoredTokens()).toEqual({ accessToken: null, refreshToken: null });
  });

  it("hydrates user from /auth/me when token exists and handles logout", async () => {
    setStoredTokens("existing-token", "existing-refresh");
    vi.spyOn(api, "me").mockResolvedValue({
      id: "u-me",
      email: "hydrated@example.com",
      full_name: "Hydrated",
      auth_provider: "google",
      avatar_url: null,
      is_active: true,
      created_at: new Date().toISOString(),
      last_login_at: null,
    });

    const user = userEvent.setup();
    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("user-email")).toHaveTextContent("hydrated@example.com"));

    await user.click(screen.getByRole("button", { name: "Sign Out" }));
    expect(screen.getByTestId("user-email")).toHaveTextContent("anonymous");
    expect(getStoredTokens().accessToken).toBeNull();
  });
});
