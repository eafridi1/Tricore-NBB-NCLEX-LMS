"use client";

import Link from "next/link";

export default function SubscriptionCancelPage() {
  return (
    <main style={{ maxWidth: 560, margin: "60px auto", fontFamily: "system-ui", padding: "0 20px", textAlign: "center" }}>
      <h1 style={{ marginBottom: 8 }}>Checkout canceled</h1>
      <p style={{ color: "#666", marginBottom: 24 }}>
        No charge was made. You can pick a plan whenever you&apos;re ready.
      </p>
      <Link
        href="/subscribe"
        style={{
          padding: "10px 20px",
          background: "#0B2540",
          color: "white",
          borderRadius: 8,
          textDecoration: "none",
        }}
      >
        View Plans
      </Link>
    </main>
  );
}