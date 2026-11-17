"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Navbar } from "@/components/ui/Navbar";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

function GoogleCallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { loginWithSession } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");
    const oauthError = searchParams.get("error");
    if (oauthError) {
      setError(`Google sign-in declined: ${oauthError}`);
      return;
    }
    if (!code) {
      setError("Missing authorization code from Google callback.");
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const redirectUri = `${window.location.origin}/auth/google/callback`;
        const session = await api.exchangeGoogleCode(code, redirectUri);
        if (!cancelled) {
          loginWithSession(session);
          router.replace("/dashboard");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Google authentication failed.");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [searchParams, loginWithSession, router]);

  return (
    <div className="mx-auto max-w-md px-4 py-20 text-center">
      <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        {error ? (
          <>
            <h1 className="font-editorial text-2xl font-semibold text-rose-700">Google Sign-In Failed</h1>
            <p className="mt-2 text-sm text-slate-600">{error}</p>
            <Link
              href="/login"
              className="mt-6 inline-block rounded-xl bg-[#0f2942] px-5 py-2.5 text-sm font-semibold text-white"
            >
              Back to Sign In
            </Link>
          </>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-[#0d9488]" />
            <h1 className="font-editorial text-2xl font-semibold text-[#0f2942]">Completing Google Sign-In</h1>
            <p className="text-sm text-slate-500">Verifying your identity and preparing your workspace...</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function GoogleCallbackPage() {
  return (
    <div className="min-h-screen bg-[#f7f8fa]">
      <Navbar />
      <Suspense
        fallback={
          <div className="flex justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-[#0d9488]" />
          </div>
        }
      >
        <GoogleCallbackHandler />
      </Suspense>
    </div>
  );
}
