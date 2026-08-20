import { useState } from "react";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type StripeCheckoutResponse = components["schemas"]["StripeCheckoutResponse"];

export function useCheckout() {
  const [loadingPlanId, setLoadingPlanId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function startCheckout(planId: number) {
    setLoadingPlanId(planId);
    setError(null);
    try {
      const { data } = await apiClient.post<StripeCheckoutResponse>(
        "/payments/stripe-checkout",
        { plan_id: planId }
      );
      window.location.href = data.checkout_url;
    } catch (err: unknown) {
      const status =
        (err as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        setError("You already have an active subscription.");
      } else {
        setError("Could not start checkout. Please try again.");
      }
      setLoadingPlanId(null);
    }
  }

  return { startCheckout, loadingPlanId, error };
}