import { useMutation } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type LoginRequest = components["schemas"]["LoginRequest"];
type LoginStep1Response = components["schemas"]["LoginStep1Response"];

export type LoginErrorKind = "invalid" | "unverified" | "locked" | "unknown";

export class LoginError extends Error {
  kind: LoginErrorKind;

  constructor(kind: LoginErrorKind, message: string) {
    super(message);
    this.kind = kind;
  }
}

function mapLoginError(error: unknown): LoginError {
  if (isAxiosError(error) && error.response) {
    switch (error.response.status) {
      case 401:
        return new LoginError("invalid", "Invalid email or password.");
      case 403:
        return new LoginError(
          "unverified",
          "Your account is not verified. Please check your email."
        );
      case 429:
        return new LoginError(
          "locked",
          "Too many attempts. Your account is temporarily locked."
        );
    }
  }
  return new LoginError("unknown", "Something went wrong. Please try again.");
}

async function loginStep1(payload: LoginRequest): Promise<LoginStep1Response> {
  try {
    const { data } = await apiClient.post<LoginStep1Response>(
      "/auth/login",
      payload
    );
    return data;
  } catch (error) {
    throw mapLoginError(error);
  }
}

export function useLogin() {
  return useMutation<LoginStep1Response, LoginError, LoginRequest>({
    mutationFn: loginStep1,
  });
}