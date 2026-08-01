import { useMutation } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { apiClient } from "@/lib/api-client";
import { setAccessToken } from "@/lib/token-store";
import { emitLogin } from "@/lib/auth-events";
import type { components } from "@/types/api";

type TwoFAVerifyRequest = components["schemas"]["TwoFAVerifyRequest"];
type TokenResponse = components["schemas"]["TokenResponse"];

export type TwoFAErrorKind =
  | "invalid_otp"
  | "expired"
  | "no_attempt"
  | "locked"
  | "unknown";

export class TwoFAError extends Error {
  kind: TwoFAErrorKind;

  constructor(kind: TwoFAErrorKind, message: string) {
    super(message);
    this.kind = kind;
  }
}

function mapTwoFAError(error: unknown): TwoFAError {
  if (isAxiosError(error) && error.response) {
    const detail: string = error.response.data?.detail ?? "";
    switch (error.response.status) {
      case 400:
        if (detail.toLowerCase().includes("expired")) {
          return new TwoFAError("expired", "This code has expired. Please log in again.");
        }
        return new TwoFAError("no_attempt", "No active login attempt found. Please log in again.");
      case 401:
        return new TwoFAError("invalid_otp", "Incorrect code. Please try again.");
      case 429:
        return new TwoFAError("locked", "Too many attempts. Please wait and try again.");
    }
  }
  return new TwoFAError("unknown", "Something went wrong. Please try again.");
}

async function verify2fa(payload: TwoFAVerifyRequest): Promise<TokenResponse> {
  try {
    const { data } = await apiClient.post<TokenResponse>(
      "/auth/2fa-verify",
      payload
    );
    setAccessToken(data.access_token);
    emitLogin(); // notify SessionProvider that we're now authenticated
    return data;
  } catch (error) {
    throw mapTwoFAError(error);
  }
}

export function use2faVerify() {
  return useMutation<TokenResponse, TwoFAError, TwoFAVerifyRequest>({
    mutationFn: verify2fa,
  });
}