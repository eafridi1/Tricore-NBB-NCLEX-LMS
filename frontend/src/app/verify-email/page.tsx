"use client";

import { useEffect, useState, useRef } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";
import { isAxiosError } from "axios";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type State =
  | { kind: "verifying" }
  | { kind: "success" }
  | { kind: "error"; message: string };

export default function VerifyEmailPage() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [state, setState] = useState<State>({ kind: "verifying" });
  const attemptedRef = useRef(false);

    useEffect(() => {
    if (!token) {
      setState({ kind: "error", message: "No verification token provided." });
      return;
    }
    if (attemptedRef.current) return;
    attemptedRef.current = true;

    (async () => {
      try {
        await apiClient.get("/auth/verify-email", { params: { token } });
        setState({ kind: "success" });
      } catch (err) {
        const detail =
          isAxiosError(err) && err.response
            ? (err.response.data as { detail?: string })?.detail
            : undefined;
        setState({
          kind: "error",
          message: detail ?? "Verification failed. The link may be invalid or expired.",
        });
      }
    })();
  }, [token]);

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-5">
      <div className="mb-6 text-center">
        <div className="text-2xl font-bold tracking-tight text-primary">NBB</div>
        <p className="mt-1 text-sm text-muted-foreground">Nurses Beyond Borders</p>
      </div>

      <Card>
        <CardContent className="grid gap-3 p-6 text-center">
          {state.kind === "verifying" && (
            <>
              <h1 className="text-lg font-semibold text-foreground">
                Verifying your email…
              </h1>
              <p className="text-sm text-muted-foreground">One moment please.</p>
            </>
          )}

          {state.kind === "success" && (
            <>
              <div className="text-3xl text-green-600">✓</div>
              <h1 className="text-lg font-semibold text-foreground">
                Email verified
              </h1>
              <p className="text-sm text-muted-foreground">
                Your account is verified. You can now sign in.
              </p>
              <Button asChild className="mt-2">
                <Link href="/login">Go to Sign in</Link>
              </Button>
            </>
          )}

          {state.kind === "error" && (
            <>
              <div className="text-3xl text-destructive">✕</div>
              <h1 className="text-lg font-semibold text-foreground">
                Verification failed
              </h1>
              <p className="text-sm text-muted-foreground">{state.message}</p>
              <Button asChild variant="outline" className="mt-2">
                <Link href="/login">Back to Sign in</Link>
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </main>
  );
}