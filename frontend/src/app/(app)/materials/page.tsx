"use client";

import { usePdfs } from "@/hooks/use-pdfs";
import { useCategories } from "@/hooks/use-categories";
import { useDownloadPdf } from "@/hooks/use-download-pdf";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function MaterialsPage() {
  const { data, isLoading, isError, error } = usePdfs();
  const { data: categories } = useCategories();
  const { download, downloadingId, error: downloadError } = useDownloadPdf();

  const categoryName = (id: number) =>
    categories?.find((c) => c.id === id)?.name ?? "General";

  return (
    <main className="mx-auto max-w-2xl px-5 py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Study Materials
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Download reference notes and study guides.
        </p>
      </div>

      {isLoading && (
        <p className="text-sm text-muted-foreground">Loading materials…</p>
      )}
      {isError && (
        <p className="text-sm text-destructive">
          {error instanceof Error ? error.message : "Failed to load materials."}
        </p>
      )}
      {downloadError && (
        <p className="mb-4 rounded-md bg-destructive/10 px-4 py-2 text-sm text-destructive">
          {downloadError}
        </p>
      )}
      {data && data.items.length === 0 && (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No study materials available yet.
          </CardContent>
        </Card>
      )}

      {data && data.items.length > 0 && (
        <ul className="grid gap-3">
          {data.items.map((pdf) => {
            const isDownloading = downloadingId === pdf.id;
            return (
              <li key={pdf.id}>
                <Card className="transition-shadow hover:shadow-md">
                  <CardContent className="flex items-start justify-between gap-3 p-4">
                    <div>
                      <div className="font-medium text-foreground">
                        {pdf.title}
                      </div>
                      {pdf.description && (
                        <div className="mt-1 text-sm text-muted-foreground">
                          {pdf.description}
                        </div>
                      )}
                      <div className="mt-1.5 text-xs text-muted-foreground/70">
                        {categoryName(pdf.category_id)}
                      </div>
                    </div>
                    <Button
                      size="sm"
                      onClick={() => download(pdf.id, pdf.title)}
                      disabled={isDownloading}
                    >
                      {isDownloading ? "Downloading…" : "Download"}
                    </Button>
                  </CardContent>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}