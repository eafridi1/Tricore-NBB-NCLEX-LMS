import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { components } from "@/types/api";

type ResendVerificationRequest =
  components["schemas"]["ResendVerificationRequest"];

async function resendVerification(body: ResendVerificationRequest): Promise<void> {
  await apiClient.post("/auth/resend-verification", body);
}

export function useResendVerification() {
  return useMutation<void, Error, ResendVerificationRequest>({
    mutationFn: resendVerification,
  });
}