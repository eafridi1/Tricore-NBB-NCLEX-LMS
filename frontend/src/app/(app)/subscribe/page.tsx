"use client";

import { usePlans } from "@/hooks/use-plans";
import { useCheckout } from "@/hooks/use-checkout";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

function formatPrice(cents: number, currency: string): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currency || "USD",
  }).format(cents / 100);
}

export default function SubscribePage() {
  const { data: plans, isLoading, isError } = usePlans();
  const { startCheckout, loadingPlanId, error } = useCheckout();

  // Highlight the longest-duration plan as "best value".
  const bestValueId =
    plans && plans.length > 0
      ? plans.reduce((a, b) => (b.duration_days > a.duration_days ? b : a)).id
      : null;

  return (
    <main className="mx-auto max-w-2xl px-5 py-10">
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Choose a Plan
        </h1>
        <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
          Unlock full access to video lessons, study materials, quizzes, and
          performance analytics.
        </p>
      </div>

      {isLoading && (
        <p className="text-center text-sm text-muted-foreground">
          Loading plans…
        </p>
      )}
      {isError && (
        <p className="text-center text-sm text-destructive">
          Failed to load plans.
        </p>
      )}
      {error && (
        <p className="mb-4 rounded-md bg-destructive/10 px-4 py-2 text-center text-sm text-destructive">
          {error}
        </p>
      )}
      {plans && plans.length === 0 && (
        <p className="text-center text-sm text-muted-foreground">
          No plans available right now.
        </p>
      )}

      {plans && plans.length > 0 && (
        <div className="grid gap-4">
          {plans.map((plan) => {
            const isRedirecting = loadingPlanId === plan.id;
            const isBestValue = plan.id === bestValueId;
            return (
              <Card
                key={plan.id}
                className={
                  isBestValue
                    ? "relative border-primary shadow-sm ring-1 ring-primary/20"
                    : "relative"
                }
              >
                {isBestValue && (
                <Badge className="absolute top-3 right-4 bg-primary text-primary-foreground hover:bg-primary">
                    Best value
                  </Badge>
                )}
                <CardContent className="flex items-center justify-between gap-4 p-5">
                  <div>
                    <div className="text-lg font-semibold text-foreground">
                      {plan.name}
                    </div>
                    {plan.description && (
                      <div className="mt-1 text-sm text-muted-foreground">
                        {plan.description}
                      </div>
                    )}
                    <div className="mt-1.5 text-xs text-muted-foreground/70">
                      {plan.duration_days} days of access
                    </div>
                  </div>

                  <div className="whitespace-nowrap text-right">
                    <div className="text-2xl font-bold text-foreground">
                      {formatPrice(plan.price_cents, plan.currency)}
                    </div>
                    <Button
                      className="mt-2"
                      onClick={() => startCheckout(plan.id)}
                      disabled={isRedirecting}
                    >
                      {isRedirecting ? "Redirecting…" : "Subscribe"}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </main>
  );
}