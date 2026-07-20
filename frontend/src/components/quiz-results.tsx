import Link from "next/link";
import type { components } from "@/types/api";

type QuizResultResponse = components["schemas"]["QuizResultResponse"];

export function QuizResults({ result }: { result: QuizResultResponse }) {
  return (
    <main style={{ maxWidth: 720, margin: "40px auto", fontFamily: "system-ui" }}>
      <div
        style={{
          padding: 20,
          borderRadius: 10,
          background: result.passed ? "#e8f5e9" : "#fdecea",
          border: `1px solid ${result.passed ? "#a5d6a7" : "#f5c6c2"}`,
          marginBottom: 28,
        }}
      >
        <h1 style={{ margin: "0 0 8px" }}>
          {result.passed ? "Passed" : "Not passed"}
        </h1>
        <div style={{ fontSize: 15 }}>
          Score: <strong>{result.score}%</strong> · {result.correct_count}/
          {result.total_questions} correct
          {result.time_taken_secs != null && (
            <> · {Math.round(result.time_taken_secs / 60)} min</>
          )}
        </div>
      </div>

      <h2 style={{ marginBottom: 16 }}>Review</h2>

      <div style={{ display: "grid", gap: 20 }}>
        {result.questions.map((qr, qi) => (
          <div
            key={qr.question_id}
            style={{ border: "1px solid #e0e0e0", borderRadius: 10, padding: 16 }}
          >
            <div style={{ fontSize: 12, color: "#888", marginBottom: 6 }}>
              Q{qi + 1} · {qr.category_name} · {qr.difficulty} ·{" "}
              <span style={{ color: qr.is_correct ? "#2e7d32" : "#c62828" }}>
                {qr.is_correct ? "Correct" : "Incorrect"}
              </span>
            </div>

            <div style={{ marginBottom: 12, lineHeight: 1.4 }}>{qr.stem}</div>

            <ul style={{ display: "grid", gap: 6, padding: 0, listStyle: "none" }}>
              {qr.options.map((opt, i) => {
                const isCorrect = i === qr.correct_answer;
                const isChosen = i === qr.chosen_answer;
                let bg = "white";
                let border = "1px solid #ddd";
                if (isCorrect) {
                  bg = "#e8f5e9";
                  border = "1px solid #a5d6a7";
                } else if (isChosen && !isCorrect) {
                  bg = "#fdecea";
                  border = "1px solid #f5c6c2";
                }
                return (
                  <li
                    key={i}
                    style={{ background: bg, border, borderRadius: 6, padding: 8 }}
                  >
                    <strong style={{ marginRight: 6 }}>
                      {String.fromCharCode(65 + i)}.
                    </strong>
                    {opt.text}
                    {isCorrect && (
                      <span style={{ color: "#2e7d32", marginLeft: 8, fontSize: 12 }}>
                        ✓ correct
                      </span>
                    )}
                    {isChosen && !isCorrect && (
                      <span style={{ color: "#c62828", marginLeft: 8, fontSize: 12 }}>
                        your answer
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>

            <div
              style={{
                marginTop: 12,
                padding: 12,
                background: "#f7f7f7",
                borderRadius: 6,
                fontSize: 14,
                lineHeight: 1.5,
              }}
            >
              <strong>Rationale:</strong> {qr.rationale}
            </div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 28 }}>
        <Link href="/dashboard" style={{ color: "#0B2540" }}>
          ← Back to dashboard
        </Link>
      </div>
    </main>
  );
}