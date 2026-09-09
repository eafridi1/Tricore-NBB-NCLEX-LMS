"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLogout } from "@/hooks/use-logout";
import { useSubscriptionCheck } from "@/hooks/use-subscription-check";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

const links = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/analytics", label: "Analytics" },
  { href: "/materials", label: "Study Materials" },
  { href: "/videos", label: "Video Lessons" },
  { href: "/announcements", label: "Announcements" },
  { href: "/bookmarks", label: "Saved Questions" },
];

function SubscriptionBadge() {
  const { data, isLoading } = useSubscriptionCheck();

  if (isLoading || !data) return null;

  if (data.has_access) {
    const isGrace = data.status === "grace";
    const days = data.days_remaining;
    return (
      <Badge
        variant="secondary"
        className={
          isGrace
            ? "whitespace-nowrap bg-amber-100 text-amber-800 hover:bg-amber-100"
            : "whitespace-nowrap bg-green-100 text-green-800 hover:bg-green-100"
        }
      >
        {isGrace ? "Grace" : "Active"}
        {typeof days === "number" ? ` · ${days}d left` : ""}
      </Badge>
    );
  }

  return (
    <Button asChild size="sm">
      <Link href="/subscribe">Subscribe</Link>
    </Button>
  );
}

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  // Avoid hydration mismatch — only render after mount (theme is client-only).
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  const isDark = theme === "dark";
  return (
    <button
      onClick={() => setTheme(isDark ? "light" : "dark")}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
      className="rounded-md border border-border px-2 py-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
    >
      {isDark ? "☀️" : "🌙"}
    </button>
  );
}

export function NavBar() {
  const pathname = usePathname();
  const logout = useLogout();

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="mx-auto flex max-w-5xl items-center gap-6 px-5 py-3">
        <Link
          href="/dashboard"
          className="text-lg font-bold tracking-tight text-primary"
        >
          NBB
        </Link>

        <nav className="flex flex-1 items-center gap-5">
          {links.map((l) => {
            const active = pathname === l.href;
            return (
              <Link
                key={l.href}
                href={l.href}
                className={
                  active
                    ? "text-sm font-semibold text-primary"
                    : "text-sm font-normal text-muted-foreground transition-colors hover:text-foreground"
                }
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        <ThemeToggle />
        <SubscriptionBadge />

        <Button asChild size="sm">
          <Link href="/quiz/start">Start Quiz</Link>
        </Button>

        <Button
          variant="outline"
          size="sm"
          onClick={() => logout.run()}
          disabled={logout.isPending}
        >
          {logout.isPending ? "…" : "Log out"}
        </Button>
      </div>
    </header>
  );
}