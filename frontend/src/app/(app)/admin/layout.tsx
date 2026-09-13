"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMe } from "@/hooks/use-me";

const adminLinks = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/students", label: "At-Risk Students" },
  { href: "/admin/questions", label: "Questions" },
];
  // future: { href: "/admin/questions", label: "Questions" }, etc.


export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { data: me, isLoading, isError } = useMe();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Redirect non-admins away once we know the role.
    if (!isLoading && me && me.role !== "admin") {
      router.replace("/dashboard");
    }
    if (isError) router.replace("/dashboard");
  }, [isLoading, isError, me, router]);

  if (isLoading) {
    return <div className="p-10 text-center text-sm text-muted-foreground">Loading…</div>;
  }
  if (!me || me.role !== "admin") {
    return null; // redirecting
  }

  return (
    <div>
      <div className="border-b border-border bg-muted/30">
        <div className="mx-auto flex max-w-5xl items-center gap-5 px-5 py-2">
          <span className="text-sm font-semibold text-foreground">Admin</span>
          <nav className="flex gap-4">
            {adminLinks.map((l) => {
              const active = pathname === l.href;
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  className={
                    active
                      ? "text-sm font-semibold text-primary"
                      : "text-sm text-muted-foreground hover:text-foreground"
                  }
                >
                  {l.label}
                </Link>
              );
            })}
          </nav>
          <Link
            href="/dashboard"
            className="ml-auto text-sm text-muted-foreground hover:text-foreground"
          >
            ← Student view
          </Link>
        </div>
      </div>
      {children}
    </div>
  );
}