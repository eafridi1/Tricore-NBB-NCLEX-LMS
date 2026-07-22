import { useState } from "react";
import { apiClient } from "@/lib/api-client";

// Parses filename from a Content-Disposition header, falling back if absent.
function filenameFromDisposition(
  disposition: string | undefined,
  fallback: string
): string {
  if (!disposition) return fallback;
  const match = /filename="?([^"]+)"?/.exec(disposition);
  return match?.[1] ?? fallback;
}

export function useDownloadPdf() {
  // Track which pdf id is currently downloading (null = none).
  const [downloadingId, setDownloadingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function download(pdfId: number, fallbackTitle: string) {
    setDownloadingId(pdfId);
    setError(null);
    try {
      const response = await apiClient.get(`/pdfs/${pdfId}/download`, {
        responseType: "blob",
      });

      const filename = filenameFromDisposition(
        response.headers["content-disposition"],
        `${fallbackTitle}.pdf`
      );

      // Turn the blob into a temporary object URL and trigger a download.
      const blob = new Blob([response.data], { type: "application/pdf" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setError("Download failed. Please try again.");
    } finally {
      setDownloadingId(null);
    }
  }

  return { download, downloadingId, error };
}