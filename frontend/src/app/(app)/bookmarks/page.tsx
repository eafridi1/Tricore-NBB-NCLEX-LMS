"use client";

import { useBookmarksReview } from "@/hooks/use-bookmarks-review";
import { useBookmark } from "@/hooks/use-bookmark";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function BookmarksPage() {
  const { data, isLoading, isError, error } = useBookmarksReview();
  const bookmark = useBookmark();
  const queryClient = useQueryClient();

  function handleRemove(questionId: number) {
    bookmark.remove.mutate(questionId, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["bookmarks-review"] });
      },
    });
  }

  return (
    <main className="mx-auto max-w-2xl px-5 py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Saved Questions
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Review the questions you bookmarked, with answers and rationales.
        </p>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {isError && (
        <p className="text-sm text-destructive">
          {error instanceof Error ? error.message : "Failed to load bookmarks."}
        </p>
      )}
      {data && data.items.length === 0 && (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            You haven&apos;t bookmarked any questions yet. Tap the ☆ on a quiz
            question to save it here.
          </CardContent>
        </Card>
      )}

      {data && data.items.length > 0 && (
        <div className="grid gap-4">
          {data.items.map((item) => (
            <Card key={item.bookmark_id}>
              <CardContent className="p-4">
                <div className="mb-2 flex items-start justify-between gap-3">
                  <div className="text-xs text-muted-foreground">
                    {item.difficulty}
                  </div>
                  <button
                    onClick={() => handleRemove(item.question_id)}
                    disabled={bookmark.isPending}
                    className="text-lg leading-none text-amber-500 hover:text-amber-600"
                    title="Remove bookmark"
                  >
                    ★
                  </button>
                </div>

                <div className="mb-3 leading-relaxed text-foreground">
                  {item.stem}
                </div>

                <ul className="grid list-none gap-1.5 p-0">
                  {item.options.map((opt, i) => {
                    const isCorrect = i === item.correct_answer;
                    return (
                      <li
                        key={i}
                        className={`rounded-md border p-2 text-sm ${
                          isCorrect
                            ? "border-green-200 bg-green-50 dark:bg-green-950/30"
                            : "border-border bg-card"
                        }`}
                      >
                        <strong className="mr-1.5">
                          {String.fromCharCode(65 + i)}.
                        </strong>
                        {(opt as { text?: string })?.text ?? String(opt)}
                        {isCorrect && (
                          <span className="ml-2 text-xs text-green-700 dark:text-green-400">
                            ✓ correct
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>

                <div className="mt-3 rounded-md bg-muted/60 p-3 text-sm leading-relaxed text-foreground/80">
                  <strong>Rationale:</strong> {item.rationale}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </main>
  );
}