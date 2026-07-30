"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/components/session-provider";
import { NavBar } from "@/components/nav-bar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const session = useSession();
  const router = useRouter();

  useEffect(() => {
    if (session === "unauthenticated") {
      router.replace("/login");
    }
  }, [session, router]);

  if (session === "unauthenticated") return null;

  return (
    <>
      <NavBar />
      {children}
    </>
  );
}