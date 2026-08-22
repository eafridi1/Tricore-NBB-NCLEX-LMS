"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSubscriptionCheck } from "@/hooks/use-subscription-check";

export default function SubscriptionSuccessPage() {
  // Poll every 2s until access is granted (webhook is async), give up after ~20s.
  const [attempts, setAttempts] = useState(0);
  const { data } = useSubscriptionCheck({
    refetchInterval: attempts < 10 ? 2000 : false,
  });

  const hasAccess = data?.has_access === true;

  useEffect(() => {
    if (!hasAccess && attempts < 10) {
      const t = setTimeout(() => setAttempts((a) => a + 1), 2000);
      return () => clearTimeout(t);
    }
  }, [hasAccess, attempts]);

  return (
    <main style={{ maxWidth: 560, margin: "60px auto", fontFamily: "system-ui", padding: "0 20px", textAlign: "center" }}>
      {hasAccess ? (
        <>
          <div style={{ fontSize: 48, marginBottom: 12 }}>✓</div>
          <h1 style={{ marginBottom: 8 }}>You&apos;re all set!</h1>
          <p style={{ color: "#666", marginBottom: 24 }}>
            Your subscription is active. You now have full access.
          </p>
          <Link
            href="/dashboard"
            style={{
              padding: "10px 20px",
              background: "#0B2540",
              color: "white",
              borderRadius: 8,
              textDecoration: "none",
            }}
          >
            Go to Dashboard
          </Link>
        </>
      ) : attempts < 10 ? (
        <>
          <h1 style={{ marginBottom: 8 }}>Confirming your payment…</h1>
          <p style={{ color: "#666" }}>
            This usually takes just a few seconds. Please wait.
          </p>
        </>
      ) : (
        <>
          <h1 style={{ marginBottom: 8 }}>Payment received</h1>
          <p style={{ color: "#666", marginBottom: 24 }}>
            Your access is being processed. If it doesn&apos;t appear shortly,
            please refresh or check your subscription status.
          </p>
          <Link href="/dashboard" style={{ color: "#0B2540" }}>
            Go to Dashboard
          </Link>
        </>
      )}
    </main>
  );
}