"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSubscriptionCheck } from "@/hooks/use-subscription-check";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function SubscriptionSuccessPage() {
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
    <main className="mx-auto max-w-md px-5 py-16">
      <Card>
        <CardContent className="p-8 text-center">
          {hasAccess ? (
            <>
              <div className="mb-3 text-4xl text-green-600">✓</div>
              <h1 className="text-xl font-semibold text-foreground">
                You&apos;re all set!
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Your subscription is active. You now have full access.
              </p>
              <Button asChild className="mt-6">
                <Link href="/dashboard">Go to Dashboard</Link>
              </Button>
            </>
          ) : attempts < 10 ? (
            <>
              <h1 className="text-xl font-semibold text-foreground">
                Confirming your payment…
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                This usually takes just a few seconds. Please wait.
              </p>
            </>
          ) : (
            <>
              <h1 className="text-xl font-semibold text-foreground">
                Payment received
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Your access is being processed. If it doesn&apos;t appear
                shortly, refresh or check your subscription status.
              </p>
              <Button asChild variant="outline" className="mt-6">
                <Link href="/dashboard">Go to Dashboard</Link>
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </main>
  );
}