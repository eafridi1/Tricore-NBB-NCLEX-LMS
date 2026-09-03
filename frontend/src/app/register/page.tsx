"use client";

import { useState } from "react";
import Link from "next/link";
import { useRegister } from "@/hooks/use-register";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function RegisterPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const register = useRegister();

  function handleSubmit() {
    register.mutate({ name, email, password });
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-5">
      <div className="mb-6 text-center">
        <div className="text-2xl font-bold tracking-tight text-primary">NBB</div>
        <p className="mt-1 text-sm text-muted-foreground">Nurses Beyond Borders</p>
      </div>

      <Card>
        <CardContent className="p-6">
          {register.isSuccess ? (
            <div className="grid gap-3 text-center">
              <div className="text-3xl text-green-600">✓</div>
              <h1 className="text-lg font-semibold text-foreground">
                Check your email
              </h1>
              <p className="text-sm text-muted-foreground">
                We&apos;ve sent a verification link to <strong>{email}</strong>.
                Verify your email, then sign in.
              </p>
              <Button asChild className="mt-2">
                <Link href="/login">Go to Sign in</Link>
              </Button>
            </div>
          ) : (
            <div className="grid gap-4">
              <h1 className="text-lg font-semibold text-foreground">
                Create your account
              </h1>

              <div className="grid gap-1.5">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>

              <div className="grid gap-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              <div className="grid gap-1.5">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <p className="text-xs text-muted-foreground/70">
                  Use at least 8 characters with a mix of letters, numbers, and symbols.
                </p>
              </div>

              <Button
                onClick={handleSubmit}
                disabled={
                  register.isPending ||
                  name.trim().length < 2 ||
                  !email ||
                  !password
                }
              >
                {register.isPending ? "Creating account…" : "Create account"}
              </Button>

              {register.isError && (
                <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {register.error.message}
                </p>
              )}

              <p className="text-center text-sm text-muted-foreground">
                Already have an account?{" "}
                <Link href="/login" className="font-medium text-primary hover:underline">
                  Sign in
                </Link>
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </main>
  );
}