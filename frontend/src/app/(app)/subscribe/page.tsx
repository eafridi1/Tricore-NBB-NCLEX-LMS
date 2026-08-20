"use client";

import { usePlans } from "@/hooks/use-plans";
import { useCheckout } from "@/hooks/use-checkout";

function formatPrice(cents: number, currency: string): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currency || "USD",
  }).format(cents / 100);
}

export default function SubscribePage() {
  const { data: plans, isLoading, isError } = usePlans();
  const { startCheckout, loadingPlanId, error } = useCheckout();

  return (
    <main style={{ maxWidth: 640, margin: "40px auto", fontFamily: "system-ui", padding: "0 20px" }}>
      <h1 style={{ marginBottom: 8 }}>Choose a Plan</h1>
      <p style={{ color: "#666", marginBottom: 24, fontSize: 15 }}>
        Subscribe to unlock full access to videos, study materials, quizzes, and analytics.
      </p>

      {isLoading && <p>Loading plans…</p>}
      {isError && <p style={{ color: "crimson" }}>Failed to load plans.</p>}
      {error && <p style={{ color: "crimson", marginBottom: 16 }}>{error}</p>}

      {plans && plans.length === 0 && <p>No plans available right now.</p>}

      {plans && plans.length > 0 && (
        <div style={{ display: "grid", gap: 16 }}>
          {plans.map((plan) => {
            const isRedirecting = loadingPlanId === plan.id;
            return (
              <div
                key={plan.id}
                style={{
                  border: "1px solid #ddd",
                  borderRadius: 10,
                  padding: 20,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: 16,
                }}
              >
                <div>
                  <div style={{ fontWeight: 700, fontSize: 18 }}>{plan.name}</div>
                  {plan.description && (
                    <div style={{ color: "#666", fontSize: 14, marginTop: 4 }}>
                      {plan.description}
                    </div>
                  )}
                  <div style={{ color: "#666", fontSize: 13, marginTop: 6 }}>
                    {plan.duration_days} days of access
                  </div>
                </div>
                <div style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  <div style={{ fontWeight: 700, fontSize: 20, marginBottom: 8 }}>
                    {formatPrice(plan.price_cents, plan.currency)}
                  </div>
                  <button
                    onClick={() => startCheckout(plan.id)}
                    disabled={isRedirecting}
                    style={{
                      padding: "8px 18px",
                      background: isRedirecting ? "#9aa8b5" : "#0B2540",
                      color: "white",
                      border: "none",
                      borderRadius: 8,
                      cursor: isRedirecting ? "default" : "pointer",
                      fontSize: 14,
                    }}
                  >
                    {isRedirecting ? "Redirecting…" : "Subscribe"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </main>
  );
}