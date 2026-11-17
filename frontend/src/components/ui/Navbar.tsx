"use client";

import { Activity, FileText, LayoutDashboard, LogOut, Plus, Sparkles } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth-context";

export function Navbar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  const navLinkClass = (href: string) => {
    const active = pathname === href || (href !== "/" && pathname.startsWith(href));
    return `inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
      active
        ? "bg-[#0f2942]/10 text-[#0f2942]"
        : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
    }`;
  };

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-6">
          <Link href={user ? "/dashboard" : "/"} className="flex items-center gap-2.5 group">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-[#0f2942] to-[#0d9488] text-white shadow-sm transition-transform group-hover:scale-105">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <span className="font-editorial text-lg font-semibold tracking-tight text-[#0f2942]">
                DocCraft
              </span>
              <span className="ml-1 rounded bg-teal-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-teal-700 border border-teal-200/70">
                AI
              </span>
            </div>
          </Link>

          {user && (
            <nav className="hidden md:flex items-center gap-1">
              <Link href="/dashboard" className={navLinkClass("/dashboard")}>
                <LayoutDashboard className="h-4 w-4" />
                Projects
              </Link>
              <Link href="/projects/new" className={navLinkClass("/projects/new")}>
                <Plus className="h-4 w-4" />
                New Document
              </Link>
              <Link href="/monitoring" className={navLinkClass("/monitoring")}>
                <Activity className="h-4 w-4" />
                Monitoring & Logs
              </Link>
            </nav>
          )}
        </div>

        <div className="flex items-center gap-3">
          {user ? (
            <>
              <div className="hidden sm:flex items-center gap-2.5 rounded-full border border-slate-200 bg-slate-50/80 py-1 pl-2 pr-3">
                {user.avatar_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={user.avatar_url}
                    alt={user.full_name}
                    className="h-6 w-6 rounded-full object-cover"
                  />
                ) : (
                  <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[#0f2942] text-xs font-semibold text-white">
                    {user.full_name.charAt(0).toUpperCase()}
                  </div>
                )}
                <div className="text-left leading-tight">
                  <div className="text-xs font-semibold text-slate-800">{user.full_name}</div>
                  <div className="text-[10px] text-slate-500">{user.email}</div>
                </div>
              </div>
              <button
                onClick={handleLogout}
                title="Sign out"
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-xs transition hover:bg-slate-50 hover:text-rose-600"
              >
                <LogOut className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Sign Out</span>
              </button>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className="rounded-lg px-3.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                Sign In
              </Link>
              <Link
                href="/register"
                className="inline-flex items-center gap-1.5 rounded-lg bg-[#0f2942] px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-[#173b5e]"
              >
                <FileText className="h-4 w-4" />
                Get Started
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
