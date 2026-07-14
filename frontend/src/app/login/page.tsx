"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useLogin } from "@/hooks/use-login";
import { use2faVerify } from "@/hooks/use-2fa-verify";

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
      {
        onSuccess: () => {
          setPhase("otp");
        },
      }
    );
  }

  function handleOtpSubmit() {
    verify.mutate(
      { email, otp },
      {
        onSuccess: () => {
          router.push("/dashboard");
        },
        onError: (err) => {
          // Both of these mean the login attempt is gone — restart step 1.
          if (err.kind === "expired" || err.kind === "no_attempt") {
            setPhase("credentials");
            setOtp("");
          }
        },
      }
    );
  }

  return (
    <main style={{ maxWidth: 360, margin: "80px auto", fontFamily: "system-ui" }}>
      <h1 style={{ marginBottom: 24 }}>Sign in</h1>

      {phase === "credentials" && (
        <div style={{ display: "grid", gap: 12 }}>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{ width: "100%", padding: 8 }}
            />
          </label>

          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{ width: "100%", padding: 8 }}
            />
          </label>

          <button
            onClick={handleCredentialsSubmit}
            disabled={login.isPending || !email || !password}
            style={{ padding: 10 }}
          >
            {login.isPending ? "Sending code…" : "Continue"}
          </button>

          {login.isError && (
            <p style={{ color: "crimson" }}>{login.error.message}</p>
          )}
        </div>
      )}

      {phase === "otp" && (
        <div style={{ display: "grid", gap: 12 }}>
          <p>We sent a 6-digit code to {email}.</p>

          <label>
            Code
            <input
              inputMode="numeric"
              maxLength={6}
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              style={{ width: "100%", padding: 8 }}
            />
          </label>

          <button
            onClick={handleOtpSubmit}
            disabled={verify.isPending || otp.length !== 6}
            style={{ padding: 10 }}
          >
            {verify.isPending ? "Verifying…" : "Verify"}
          </button>

          {verify.isError && (
            <p style={{ color: "crimson" }}>{verify.error.message}</p>
          )}
        </div>
      )}
    </main>
  );
}