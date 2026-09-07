"use client";

import { useState } from "react";
import Link from "next/link";
import { useResendVerification } from "@/hooks/use-resend-verification";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function ResendVerificationPage() {
  const [email, setEmail] = useState("");
  const resend = useResendVerification();

  function handleSubmit() {
    resend.mutate({ email });
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-5">
      <div className="mb-6 text-center">
        <div className="text-2xl font-bold tracking-tight text-primary">NBB</div>
        <p className="mt-1 text-sm text-muted-foreground">Nurses Beyond Borders</p>
      </div>

      <Card>
        <CardContent className="p-6">
          {resend.isSuccess ? (
            <div className="grid gap-3 text-center">
              <div className="text-3xl text-green-600">✓</div>
              <h1 className="text-lg font-semibold text-foreground">
                Check your email
              </h1>
              <p className="text-sm text-muted-foreground">
                If an account with that email exists and isn&apos;t yet verified,
                we&apos;ve sent a new verification link.
              </p>
              <Button asChild className="mt-2">
                <Link href="/login">Back to Sign in</Link>
              </Button>
            </div>
          ) : (
            <div className="grid gap-4">
              <h1 className="text-lg font-semibold text-foreground">
                Resend verification email
              </h1>
              <p className="text-sm text-muted-foreground">
                Enter your email and we&apos;ll send a new verification link if
                your account still needs verifying.
              </p>

              <div className="grid gap-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && email && handleSubmit()}
                />
              </div>

              <Button onClick={handleSubmit} disabled={resend.isPending || !email}>
                {resend.isPending ? "Sending…" : "Send verification link"}
              </Button>

              <p className="text-center text-sm text-muted-foreground">
                Back to{" "}
                <Link href="/login" className="font-medium text-primary hover:underline">
                  Sign in
                </Link>
                              <Button asChild variant="outline" className="mt-2">
                <Link href="/login">Back to Sign in</Link>
              </Button>
              <Link
                href="/resend-verification"
                className="text-sm text-primary hover:underline"
              >
                Request a new verification link
              </Link>
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </main>
  );
}