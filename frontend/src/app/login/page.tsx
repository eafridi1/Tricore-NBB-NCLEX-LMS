"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useLogin } from "@/hooks/use-login";
import { use2faVerify } from "@/hooks/use-2fa-verify";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Phase = "credentials" | "otp";

export default function LoginPage() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("credentials");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const login = useLogin();
  const verify = use2faVerify();

  function handleCredentialsSubmit() {
    login.mutate(
      { email, password },
      { onSuccess: () => setPhase("otp") }
    );
  }

  function handleOtpSubmit() {
    verify.mutate(
      { email, otp },
      {
        onSuccess: () => router.push("/dashboard"),
        onError: (err) => {
          if (err.kind === "expired" || err.kind === "no_attempt") {
            setPhase("credentials");
            setOtp("");
          }
        },
      }
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-5">
      <div className="mb-6 text-center">
        <div className="text-2xl font-bold tracking-tight text-primary">NBB</div>
        <p className="mt-1 text-sm text-muted-foreground">
          Nurses Beyond Borders
        </p>
      </div>

      <Card>
        <CardContent className="p-6">
          {phase === "credentials" && (
            <div className="grid gap-4">
              <h1 className="text-lg font-semibold text-foreground">Sign in</h1>

              <div className="grid gap-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && email && password && handleCredentialsSubmit()}
                />
              </div>

              <div className="grid gap-1.5">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && email && password && handleCredentialsSubmit()}
                />
              </div>

              <Button
                onClick={handleCredentialsSubmit}
                disabled={login.isPending || !email || !password}
              >
                {login.isPending ? "Sending code…" : "Continue"}
              </Button>

              {login.isError && (
                <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {login.error.message}
                </p>
              )}
            </div>
          )}

          {phase === "otp" && (
            <div className="grid gap-4">
              <h1 className="text-lg font-semibold text-foreground">
                Enter your code
              </h1>
              <p className="text-sm text-muted-foreground">
                We sent a 6-digit code to {email}.
              </p>

              <div className="grid gap-1.5">
                <Label htmlFor="otp">Code</Label>
                <Input
                  id="otp"
                  inputMode="numeric"
                  maxLength={6}
                  value={otp}
                  onChange={(e) => setOtp(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && otp.length === 6 && handleOtpSubmit()}
                />
              </div>

              <Button
                onClick={handleOtpSubmit}
                disabled={verify.isPending || otp.length !== 6}
              >
                {verify.isPending ? "Verifying…" : "Verify"}
              </Button>

              {verify.isError && (
                <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {verify.error.message}
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </main>
  );
}