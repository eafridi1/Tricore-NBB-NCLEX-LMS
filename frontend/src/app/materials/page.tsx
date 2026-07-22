"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSession } from "@/components/session-provider";
import { usePdfs } from "@/hooks/use-pdfs";
import { useCategories } from "@/hooks/use-categories";
import { useDownloadPdf } from "@/hooks/use-download-pdf";

export default function MaterialsPage() {
  const session = useSession();
  const router = useRouter();

  useEffect(() => {
    if (session === "unauthenticated") {
      router.replace("/login");
    }
  }, [session, router]);

  const { data, isLoading, isError, error } = usePdfs();
  const { data: categories } = useCategories();
  const { download, downloadingId, error: downloadError } = useDownloadPdf();

  if (session === "unauthenticated") return null;

  const categoryName = (id: number) =>
    categories?.find((c) => c.id === id)?.name ?? "General";

  return (
    <main style={{ maxWidth: 640, margin: "60px auto", fontFamily: "system-ui" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 24,
        }}
      >
        <h1 style={{ margin: 0 }}>Study Materials</h1>
        <Link href="/dashboard" style={{ fontSize: 14, color: "#0B2540" }}>
          ← Dashboard
        </Link>
      </div>

      {isLoading && <p>Loading materials…</p>}

      {isError && (
        <p style={{ color: "crimson" }}>
          {error instanceof Error ? error.message : "Failed to load materials."}
        </p>
      )}

      {downloadError && <p style={{ color: "crimson" }}>{downloadError}</p>}

      {data && data.items.length === 0 && <p>No study materials available yet.</p>}

      {data && data.items.length > 0 && (
        <ul style={{ display: "grid", gap: 12, padding: 0, listStyle: "none" }}>
          {data.items.map((pdf) => {
            const isDownloading = downloadingId === pdf.id;
            return (
              <li
                key={pdf.id}
                style={{ border: "1px solid #ddd", borderRadius: 8, padding: 14 }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    gap: 12,
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>{pdf.title}</div>
                    {pdf.description && (
                      <div style={{ fontSize: 14, color: "#666", marginTop: 4 }}>
                        {pdf.description}
                      </div>
                    )}
                    <div style={{ fontSize: 12, color: "#999", marginTop: 6 }}>
                      {categoryName(pdf.category_id)}
                    </div>
                  </div>
                  <button
                    onClick={() => download(pdf.id, pdf.title)}
                    disabled={isDownloading}
                    style={{
                      padding: "8px 14px",
                      background: isDownloading ? "#9aa8b5" : "#0B2540",
                      color: "white",
                      border: "none",
                      borderRadius: 8,
                      cursor: isDownloading ? "default" : "pointer",
                      whiteSpace: "nowrap",
                      fontSize: 14,
                    }}
                  >
                    {isDownloading ? "Downloading…" : "Download"}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}