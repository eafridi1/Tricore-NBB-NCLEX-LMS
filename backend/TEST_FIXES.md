# Test suite fixes — 2026-07-02

Ran the backend test suite (`pytest`, 99 tests). It was not passing cleanly:
every test errored during teardown, and 3 tests genuinely failed. All 99
tests pass now. Details below.

## 1. Every test errored on teardown (`RuntimeError: Event loop is closed`)

**Where:** [pytest.ini](pytest.ini)

**Symptom:** Every single test showed as `PASSED` followed immediately by a
separate `ERROR` at teardown:

```
RuntimeError: Event loop is closed
AttributeError: 'NoneType' object has no attribute 'send'
```

This wasn't just noise — it was silently leaking a Postgres connection per
test (confirmed via `netstat`, connection count climbed steadily), which
would eventually exhaust `max_connections` and hang the whole suite.

**Cause:** `pytest.ini` set `asyncio_default_fixture_loop_scope = session`
but left the test loop scope at its default, `function`. That means every
async fixture (`db`, `client`, `student_user`, ...) ran on one shared
event loop for the whole session, while each test body ran on a brand-new
event loop created just for that test. The `db` fixture opens its asyncpg
connection while running on the session loop, but the test itself (via the
`client` fixture's HTTP calls into the app) drives that same connection
from the function loop. When the function loop closed at the end of the
test, the asyncpg connection's internal callbacks — still scheduled against
that now-closed loop — blew up on the next attempted operation (the
`TRUNCATE`/`engine.dispose()` teardown in `db`).

**Fix:** Changed `asyncio_default_fixture_loop_scope` from `session` to
`function` so fixtures and the test body run on the same loop. The `db`
fixture already creates and disposes a fresh engine per test, so it was
already designed for function-scoped isolation — the config just didn't
match.

## 2. `test_delete_category_ok_when_all_questions_soft_deleted` — FAILED

**Where:** [routers/categories.py](routers/categories.py) `delete_category`,
[models.py](models.py) `Question.category_id`

**Symptom:**

```
asyncpg.exceptions.ForeignKeyViolationError: update or delete on table
"categories" violates foreign key constraint "questions_category_id_fkey"
on table "questions"
```

**Cause:** `delete_category` only blocks deletion when a *live*
(`is_deleted=False`) question references the category — the intent (per
the code's own comment) was that soft-deleted questions shouldn't block
deletion since they're invisible everywhere. But that check only guards
the 409 response; it does nothing about the actual foreign key. A
soft-deleted question row still physically exists with `category_id`
pointing at the row being deleted, and `category_id` was `NOT NULL`, so
Postgres correctly refused the `DELETE FROM categories` regardless of the
app-level soft-delete flag.

**Fix:**
- Made `Question.category_id` nullable (`models.py`), plus a new Alembic
  migration ([migrations/versions/7c29cf2e2bcc_make_questions_category_id_nullable.py](migrations/versions/7c29cf2e2bcc_make_questions_category_id_nullable.py))
  to relax the same column on a real database.
- `delete_category` now nulls out `category_id` on any soft-deleted
  questions still pointing at the category *before* deleting it, instead
  of hard-deleting those rows. This preserves the existing invariant
  (documented on `Question.is_deleted`) that soft-deleted questions stay
  resolvable forever for historical `quiz_attempts` results — a hard
  delete here would have silently broken that.
- `routers/quizzes.py`'s `get_result` endpoint already falls back to a
  `"Unknown"` category name when the category lookup comes back empty;
  it just wasn't guarding against `question.category_id` itself being
  `None`. Added that guard (`db.get(Category, None)` triggers a
  SQLAlchemy `SAWarning` today and is flagged to become a hard error in a
  future release) so the existing fallback path keeps working.

## 3 & 4. `test_save_answer_success` / `test_save_answer_overwrites_previous` — FAILED

**Where:** [models.py](models.py) `QuizAttempt.answers` / `.question_ids` /
`Question.options`, [routers/quizzes.py](routers/quizzes.py) `save_answer`

Two separate bugs stacked on the same line of code.

### 3a. Wrong column type: `json` instead of `jsonb`

**Symptom (first pass):**

```
asyncpg.exceptions.UndefinedFunctionError: operator does not exist: json || jsonb
```

**Cause:** `save_answer` merges a new answer into the `answers` column
with the Postgres `||` (jsonb concatenation) operator — but
`QuizAttempt.answers` (and `.question_ids`, and `Question.options`) were
declared as plain `JSON` in `models.py`, while the actual Alembic
migrations that created these columns
([23668c95dc3d_add_categories_questions_bookmarks.py](migrations/versions/23668c95dc3d_add_categories_questions_bookmarks.py),
[fef87edf1c95_add_quiz_attempts.py](migrations/versions/fef87edf1c95_add_quiz_attempts.py))
correctly used `postgresql.JSONB`. Since the test database is built
straight from `models.py` (`Base.metadata.create_all()` in
`tests/conftest.py`), it got the mismatched `json` type. `||` between
`json` and `jsonb` isn't defined in Postgres, hence the error. Any
fresh environment built from `models.py` alone (not just tests) would
have hit the same wall in production.

**Fix:** Changed `options`, `question_ids`, and `answers` in `models.py`
to `postgresql.JSONB`, matching what the migrations already create.

### 3b. `literal()` dict not typed as JSONB before binding

**Symptom (after fixing 3a):**

```
asyncpg.exceptions.DataError: invalid input for query argument $1:
{'1': 0} ('dict' object has no attribute 'encode')
```

**Cause:** `save_answer` built the merge value with
`cast(literal({...}), JSONB)`. `literal()` without an explicit `type_=`
infers a bind parameter type from the Python value — for a `dict` it
doesn't resolve to anything that knows how to JSON-serialize, so asyncpg
received the raw Python `dict` as a bind parameter and tried to treat it
like a string, which failed. The outer `cast(..., JSONB)` only affects
how Postgres interprets the value *after* it arrives — it doesn't fix
how the value gets serialized on the way there.

**Fix:** Pass `type_=JSONB` directly to `literal()` so SQLAlchemy
JSON-serializes the dict before sending it:

```python
new_answer = cast(
    literal({str(data.question_id): data.chosen_index}, type_=JSONB), JSONB
)
```

## Result

```
99 passed in 51.22s
```

## Files changed

- `pytest.ini` — fixture/test loop scope mismatch
- `models.py` — `Question.category_id` nullable; `Question.options`,
  `QuizAttempt.question_ids`, `QuizAttempt.answers` changed `JSON` → `JSONB`
- `routers/categories.py` — `delete_category` nulls out soft-deleted
  questions' `category_id` before deleting the category
- `routers/quizzes.py` — guard `db.get(Category, None)` in `get_result`;
  fix `literal()` typing in `save_answer`
- `migrations/versions/7c29cf2e2bcc_make_questions_category_id_nullable.py`
  (new) — matches the `models.py` nullability change for a real database
