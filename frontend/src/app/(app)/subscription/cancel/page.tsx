"use client";

import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function SubscriptionCancelPage() {
  return (
    <main className="mx-auto max-w-md px-5 py-16">
      <Card>
        <CardContent className="p-8 text-center">
          <h1 className="text-xl font-semibold text-foreground">
            Checkout canceled
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            No charge was made. You can pick a plan whenever you&apos;re ready.
          </p>
          <Button asChild className="mt-6">
            <Link href="/subscribe">View Plans</Link>
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}