"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLogout } from "@/hooks/use-logout";
import { useSubscriptionCheck } from "@/hooks/use-subscription-check";

const links = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/analytics", label: "Analytics" },
  { href: "/materials", label: "Study Materials" },
  { href: "/announcements", label: "Announcements" },
];

function SubscriptionBadge() {
  const { data, isLoading } = useSubscriptionCheck();

  if (isLoading || !data) return null;

  // Active or grace → show a status pill with days remaining.
  if (data.has_access) {
    const isGrace = data.status === "grace";
    const days = data.days_remaining;
    return (
      <span
        style={{
          fontSize: 12,
          fontWeight: 600,
          padding: "4px 10px",
          borderRadius: 999,
          background: isGrace ? "#fff4e5" : "#e8f5e9",
          color: isGrace ? "#b26a00" : "#2e7d32",
          whiteSpace: "nowrap",
        }}
      >
        {isGrace ? "Grace" : "Active"}
        {typeof days === "number" ? ` · ${days}d left` : ""}
      </span>
    );
  }

  // No access → a subscribe prompt.
  return (
    <Link
      href="/subscribe"
      style={{
        fontSize: 13,
        fontWeight: 600,
        padding: "6px 12px",
        borderRadius: 8,
        background: "#0B2540",
        color: "white",
        textDecoration: "none",
        whiteSpace: "nowrap",
      }}
    >
      Subscribe
    </Link>
  );
}

export function NavBar() {
  const pathname = usePathname();
  const logout = useLogout();

  return (
    <header
      style={{
        borderBottom: "1px solid #e5e5e5",
        background: "white",
        fontFamily: "system-ui",
      }}
    >
      <div
        style={{
          maxWidth: 960,
          margin: "0 auto",
          padding: "12px 20px",
          display: "flex",
          alignItems: "center",
          gap: 24,
        }}
      >
        <Link
          href="/dashboard"
          style={{
            fontWeight: 700,
            fontSize: 18,
            color: "#0B2540",
            textDecoration: "none",
          }}
        >
          NBB
        </Link>

        <nav style={{ display: "flex", gap: 18, flex: 1 }}>
          {links.map((l) => {
            const active = pathname === l.href;
            return (
              <Link
                key={l.href}
                href={l.href}
                style={{
                  fontSize: 14,
                  color: active ? "#0B2540" : "#666",
                  fontWeight: active ? 600 : 400,
                  textDecoration: "none",
                }}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>

        <SubscriptionBadge />

        <Link
          href="/quiz/start"
          style={{
            padding: "8px 14px",
            background: "#0B2540",
            color: "white",
            borderRadius: 8,
            textDecoration: "none",
            fontSize: 14,
          }}
        >
          Start Quiz
        </Link>

        <button
          onClick={() => logout.run()}
          disabled={logout.isPending}
          style={{
            padding: "8px 12px",
            background: "none",
            border: "1px solid #ddd",
            borderRadius: 8,
            fontSize: 14,
            cursor: logout.isPending ? "default" : "pointer",
            color: "#666",
          }}
        >
          {logout.isPending ? "…" : "Log out"}
        </button>
      </div>
    </header>
  );
}