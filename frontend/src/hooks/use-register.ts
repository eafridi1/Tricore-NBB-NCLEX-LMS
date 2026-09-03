import { useMutation } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type RegisterRequest = components["schemas"]["RegisterRequest"];
type RegisterResponse = components["schemas"]["RegisterResponse"];

export type RegisterErrorKind = "duplicate" | "weak_password" | "invalid" | "unknown";

export class RegisterError extends Error {
  kind: RegisterErrorKind;
  constructor(kind: RegisterErrorKind, message: string) {
    super(message);
    this.kind = kind;
    this.name = "RegisterError";
  }
}

async function register(body: RegisterRequest): Promise<RegisterResponse> {
  try {
    const { data } = await apiClient.post<RegisterResponse>("/auth/register", body);
    return data;
  } catch (err) {
    if (isAxiosError(err) && err.response) {
      const status = err.response.status;
      const detail =
        (err.response.data as { detail?: string })?.detail ?? "";
      if (status === 409) {
        throw new RegisterError("duplicate", "An account with this email already exists.");
      }
      if (status === 422) {
        // Validation error — likely weak password or bad input.
        const msg = typeof detail === "string" && detail
          ? detail
          : "Please check your details. Your password may not meet the requirements.";
        throw new RegisterError("weak_password", msg);
      }
      throw new RegisterError("unknown", "Registration failed. Please try again.");
    }
    throw new RegisterError("unknown", "Registration failed. Please try again.");
  }
}

export function useRegister() {
  return useMutation<RegisterResponse, RegisterError, RegisterRequest>({
    mutationFn: register,
  });
}