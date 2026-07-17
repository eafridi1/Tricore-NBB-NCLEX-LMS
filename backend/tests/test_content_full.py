# backend/tests/test_content_full.py
"""
Full coverage for Week 3 content endpoints not covered in test_content.py:
- GET /videos/{id}, POST /videos (admin), PATCH /videos/{id}, DELETE /videos/{id}
- GET /pdfs, GET /pdfs/{id}/download (bytes check), POST/PATCH/DELETE /pdfs (admin)
- GET /bookmarks
- PATCH /announcements/{id}, DELETE /announcements/{id}
"""

import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models import (
    Announcement, Video, VideoProgress, PDF, Category,
    Bookmark, Question, QStatus, Difficulty, User,
)
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


# ── Seed helpers ──────────────────────────────────────────────────────────────

async def _seed_category(db: AsyncSession, name: str) -> Category:
    cat = Category(name=name, sort_order=0)
    db.add(cat)
    await db.flush()
    await db.refresh(cat)
    return cat


async def _seed_video(
    db: AsyncSession, category_id: int, is_published: bool = True
) -> Video:
    v = Video(
        title="Test Video",
        category_id=category_id,
        storage_url="videos/test.mp4",
        duration_secs=900,
        sort_order=0,
        is_published=is_published,
    )
    db.add(v)
    await db.flush()
    await db.refresh(v)
    return v


async def _seed_pdf(
    db: AsyncSession, category_id: int, is_published: bool = True
) -> PDF:
    p = PDF(
        title="Test PDF",
        category_id=category_id,
        storage_url="pdfs/test.pdf",
        sort_order=0,
        is_published=is_published,
    )
    db.add(p)
    await db.flush()
    await db.refresh(p)
    return p


async def _seed_announcement(
    db: AsyncSession, admin_id: int,
    title: str = "Ann",
    is_published: bool = True,
) -> Announcement:
    a = Announcement(
        title=title, body="Body.",
        is_published=is_published,
        published_at=datetime.now(timezone.utc) if is_published else None,
        created_by=admin_id,
    )
    db.add(a)
    await db.flush()
    await db.refresh(a)
    return a


async def _seed_question(
    db: AsyncSession, category_id: int, admin_id: int
) -> Question:
    q = Question(
        stem="stem", options=[{"text": x} for x in "ABCD"],
        correct_answer=0, rationale="r",
        category_id=category_id, nclex_domain="d",
        difficulty=Difficulty.easy, status=QStatus.published,
        is_deleted=False, created_by=admin_id,
    )
    db.add(q)
    await db.flush()
    await db.refresh(q)
    return q


# ── GET /videos/{video_id} ────────────────────────────────────────────────────

async def test_get_video_returns_stream_url_and_progress(
    client: AsyncClient, db: AsyncSession, student_user, student_token: str
):
    cat = await _seed_category(db, "GetVideoCat")
    video = await _seed_video(db, cat.id)

    resp = await client.get(
        f"/videos/{video.id}",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == video.id
    assert "stream_url" in data
    assert data["stream_url"]  # not empty
    assert data["percent_watched"] == 0.0  # no progress yet


async def test_get_video_shows_saved_progress(
    client: AsyncClient, db: AsyncSession, student_user, student_token: str
):
    cat = await _seed_category(db, "ProgressVideoCat")
    video = await _seed_video(db, cat.id)

    # Seed existing progress
    db.add(VideoProgress(
        user_id=student_user.id,
        video_id=video.id,
        percent_watched=60,
    ))
    await db.flush()

    resp = await client.get(
        f"/videos/{video.id}",
        headers=auth_headers(student_token),
    )
    assert resp.json()["percent_watched"] == 60.0


async def test_get_video_unpublished_student_gets_404(
    client: AsyncClient, db: AsyncSession, student_token: str
):
    cat = await _seed_category(db, "UnpubVideoCat")
    video = await _seed_video(db, cat.id, is_published=False)

    resp = await client.get(
        f"/videos/{video.id}",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 404


async def test_get_video_unpublished_admin_can_see(
    client: AsyncClient, db: AsyncSession, admin_token: str
):
    cat = await _seed_category(db, "AdminUnpubCat")
    video = await _seed_video(db, cat.id, is_published=False)

    resp = await client.get(
        f"/videos/{video.id}",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200


async def test_get_video_not_found(client: AsyncClient, student_token: str):
    resp = await client.get("/videos/99999", headers=auth_headers(student_token))
    assert resp.status_code == 404


# ── POST /videos (admin) ─────────────────────────────────────────────────────

async def test_create_video_admin_success(
    client: AsyncClient, db: AsyncSession, admin_token: str
):
    cat = await _seed_category(db, "CreateVideoCat")

    resp = await client.post(
        "/videos",
        json={
            "title": "New Lecture",
            "category_id": cat.id,
            "storage_url": "videos/new-lecture.mp4",
            "duration_secs": 1200,
            "sort_order": 1,
        },
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "New Lecture"
    assert data["is_published"] is False  # always starts unpublished


async def test_create_video_student_forbidden(
    client: AsyncClient, db: AsyncSession, student_token: str
):
    cat = await _seed_category(db, "StudentVideoCat")
    resp = await client.post(
        "/videos",
        json={"title": "X", "category_id": cat.id, "storage_url": "v/x.mp4"},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 403


async def test_create_video_invalid_category(
    client: AsyncClient, admin_token: str
):
    resp = await client.post(
        "/videos",
        json={"title": "X", "category_id": 99999, "storage_url": "v/x.mp4"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 400


# ── PATCH /videos/{video_id} (admin) ─────────────────────────────────────────

async def test_update_video_publish(
    client: AsyncClient, db: AsyncSession, admin_token: str
):
    cat = await _seed_category(db, "PatchVideoCat")
    video = await _seed_video(db, cat.id, is_published=False)

    resp = await client.patch(
        f"/videos/{video.id}",
        json={"is_published": True},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_published"] is True


async def test_update_video_partial_does_not_clear_title(
    client: AsyncClient, db: AsyncSession, admin_token: str
):
    cat = await _seed_category(db, "PartialVideoCat")
    video = await _seed_video(db, cat.id)
    original_title = video.title

    resp = await client.patch(
        f"/videos/{video.id}",
        json={"is_published": False},
        headers=auth_headers(admin_token),
    )
    assert resp.json()["title"] == original_title


async def test_update_video_not_found(client: AsyncClient, admin_token: str):
    resp = await client.patch(
        "/videos/99999", json={"is_published": True},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 404


async def test_update_video_student_forbidden(
    client: AsyncClient, db: AsyncSession, student_token: str
):
    cat = await _seed_category(db, "StudentPatchVideoCat")
    video = await _seed_video(db, cat.id)
    resp = await client.patch(
        f"/videos/{video.id}", json={"is_published": True},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 403


# ── DELETE /videos/{video_id} (admin) ────────────────────────────────────────

async def test_delete_video_success(
    client: AsyncClient, db: AsyncSession, admin_token: str
):
    cat = await _seed_category(db, "DelVideoCat")
    video = await _seed_video(db, cat.id)

    resp = await client.delete(
        f"/videos/{video.id}",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert await db.get(Video, video.id) is None


async def test_delete_video_not_found(client: AsyncClient, admin_token: str):
    resp = await client.delete("/videos/99999", headers=auth_headers(admin_token))
    assert resp.status_code == 404


async def test_delete_video_student_forbidden(
    client: AsyncClient, db: AsyncSession, student_token: str
):
    cat = await _seed_category(db, "StudentDelVideoCat")
    video = await _seed_video(db, cat.id)
    resp = await client.delete(
        f"/videos/{video.id}", headers=auth_headers(student_token)
    )
    assert resp.status_code == 403


# ── GET /pdfs ─────────────────────────────────────────────────────────────────

async def test_list_pdfs_student_sees_published_only(
    client: AsyncClient, db: AsyncSession, student_token: str
):
    cat = await _seed_category(db, "PDFListCat")
    published = await _seed_pdf(db, cat.id, is_published=True)
    draft = await _seed_pdf(db, cat.id, is_published=False)

    resp = await client.get("/pdfs", headers=auth_headers(student_token))
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert published.id in ids
    assert draft.id not in ids


async def test_list_pdfs_admin_sees_unpublished(
    client: AsyncClient, db: AsyncSession, admin_token: str
):
    cat = await _seed_category(db, "PDFAdminCat")
    draft = await _seed_pdf(db, cat.id, is_published=False)

    resp = await client.get("/pdfs", headers=auth_headers(admin_token))
    ids = [i["id"] for i in resp.json()["items"]]
    assert draft.id in ids


async def test_list_pdfs_filter_by_category(
    client: AsyncClient, db: AsyncSession, student_token: str
):
    cat1 = await _seed_category(db, "PDFFilterCat1")
    cat2 = await _seed_category(db, "PDFFilterCat2")
    p1 = await _seed_pdf(db, cat1.id)
    await _seed_pdf(db, cat2.id)

    resp = await client.get(
        f"/pdfs?category_id={cat1.id}",
        headers=auth_headers(student_token),
    )
    ids = [i["id"] for i in resp.json()["items"]]
    assert p1.id in ids
    for item in resp.json()["items"]:
        assert item["category_id"] == cat1.id


async def test_list_pdfs_requires_auth(client: AsyncClient):
    resp = await client.get("/pdfs")
    assert resp.status_code in (401, 403)


# ── GET /pdfs/{id}/download ───────────────────────────────────────────────────

async def test_download_pdf_returns_pdf_bytes(
    client: AsyncClient, db: AsyncSession, student_token: str
):
    """
    PDF download returns actual PDF bytes with correct headers.
    Mocks _fetch_and_watermark so this test doesn't require
    pypdf/reportlab to be installed in the test environment.
    The watermark library integration is covered by the Day 6
    manual checklist (open the file in a PDF viewer).
    """
    from unittest.mock import patch

    cat = await _seed_category(db, "DLPDFCat")
    pdf = await _seed_pdf(db, cat.id)

    # Minimal valid PDF bytes — %PDF magic header so Content-Type is correct
    fake_pdf = b"%PDF-1.4 fake-watermarked-content"

    with patch("routers.pdfs._fetch_and_watermark", return_value=fake_pdf):
        resp = await client.get(
            f"/pdfs/{pdf.id}/download",
            headers=auth_headers(student_token),
        )

    assert resp.status_code == 200
    assert "application/pdf" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.content == fake_pdf


async def test_download_pdf_filename_contains_user_id(
    client: AsyncClient, db: AsyncSession, student_user, student_token: str
):
    from unittest.mock import patch

    cat = await _seed_category(db, "FilenameCat")
    pdf = await _seed_pdf(db, cat.id)

    fake_pdf = b"%PDF-1.4 fake"

    with patch("routers.pdfs._fetch_and_watermark", return_value=fake_pdf):
        resp = await client.get(
            f"/pdfs/{pdf.id}/download",
            headers=auth_headers(student_token),
        )

    assert resp.status_code == 200
    disposition = resp.headers["content-disposition"]
    assert str(student_user.id) in disposition


async def test_download_pdf_two_users_different_filenames(
    client: AsyncClient, db: AsyncSession,
    student_user, admin_user, student_token: str, admin_token: str
):
    """
    Different users get different Content-Disposition filenames because
    the filename includes user_id (e.g. Test_PDF-1.pdf vs Test_PDF-2.pdf).

    NOTE: With the logo watermark, the PDF bytes themselves are now IDENTICAL
    for all users (same logo, no per-user text). The per-user differentiation
    is in the filename only. If student identity tracing is re-enabled
    (see _create_watermark_page comments), bytes will differ again.
    """
    from unittest.mock import patch

    cat = await _seed_category(db, "WatermarkCat")
    pdf = await _seed_pdf(db, cat.id)

    fake_pdf = b"%PDF-1.4 fake"

    with patch("routers.pdfs._fetch_and_watermark", return_value=fake_pdf):
        student_resp = await client.get(
            f"/pdfs/{pdf.id}/download",
            headers=auth_headers(student_token),
        )
        admin_resp = await client.get(
            f"/pdfs/{pdf.id}/download",
            headers=auth_headers(admin_token),
        )

    assert student_resp.status_code == 200
    assert admin_resp.status_code == 200
    # Filenames differ because they contain different user IDs
    assert (
        student_resp.headers["content-disposition"]
        != admin_resp.headers["content-disposition"]
    )


async def test_download_pdf_unpublished_student_gets_404(
    client: AsyncClient, db: AsyncSession, student_token: str
):
    cat = await _seed_category(db, "UnpubPDFCat")
    pdf = await _seed_pdf(db, cat.id, is_published=False)

    resp = await client.get(
        f"/pdfs/{pdf.id}/download",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 404


async def test_download_pdf_not_found(client: AsyncClient, student_token: str):
    resp = await client.get("/pdfs/99999/download", headers=auth_headers(student_token))
    assert resp.status_code == 404


async def test_download_pdf_requires_auth(
    client: AsyncClient, db: AsyncSession
):
    cat = await _seed_category(db, "AuthPDFCat")
    pdf = await _seed_pdf(db, cat.id)
    resp = await client.get(f"/pdfs/{pdf.id}/download")
    assert resp.status_code in (401, 403)


# ── POST /pdfs (admin) ────────────────────────────────────────────────────────

async def test_create_pdf_admin_success(
    client: AsyncClient, db: AsyncSession, admin_token: str
):
    cat = await _seed_category(db, "CreatePDFCat")
    resp = await client.post(
        "/pdfs",
        json={"title": "New Notes", "category_id": cat.id, "storage_url": "pdfs/new.pdf"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "New Notes"
    assert resp.json()["is_published"] is False


async def test_create_pdf_student_forbidden(
    client: AsyncClient, db: AsyncSession, student_token: str
):
    cat = await _seed_category(db, "StudentPDFCat")
    resp = await client.post(
        "/pdfs",
        json={"title": "X", "category_id": cat.id, "storage_url": "pdfs/x.pdf"},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 403


async def test_create_pdf_invalid_category(
    client: AsyncClient, admin_token: str
):
    resp = await client.post(
        "/pdfs",
        json={"title": "X", "category_id": 99999, "storage_url": "pdfs/x.pdf"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 400


# ── PATCH /pdfs/{id} (admin) ─────────────────────────────────────────────────

async def test_update_pdf_publish(
    client: AsyncClient, db: AsyncSession, admin_token: str
):
    cat = await _seed_category(db, "PatchPDFCat")
    pdf = await _seed_pdf(db, cat.id, is_published=False)

    resp = await client.patch(
        f"/pdfs/{pdf.id}",
        json={"is_published": True},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_published"] is True


async def test_update_pdf_not_found(client: AsyncClient, admin_token: str):
    resp = await client.patch(
        "/pdfs/99999", json={"is_published": True},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 404


async def test_update_pdf_student_forbidden(
    client: AsyncClient, db: AsyncSession, student_token: str
):
    cat = await _seed_category(db, "StudentPatchPDFCat")
    pdf = await _seed_pdf(db, cat.id)
    resp = await client.patch(
        f"/pdfs/{pdf.id}", json={"is_published": False},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 403


# ── DELETE /pdfs/{id} (admin) ─────────────────────────────────────────────────

async def test_delete_pdf_success(
    client: AsyncClient, db: AsyncSession, admin_token: str
):
    cat = await _seed_category(db, "DelPDFCat")
    pdf = await _seed_pdf(db, cat.id)

    resp = await client.delete(f"/pdfs/{pdf.id}", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert await db.get(PDF, pdf.id) is None


async def test_delete_pdf_not_found(client: AsyncClient, admin_token: str):
    resp = await client.delete("/pdfs/99999", headers=auth_headers(admin_token))
    assert resp.status_code == 404


async def test_delete_pdf_student_forbidden(
    client: AsyncClient, db: AsyncSession, student_token: str
):
    cat = await _seed_category(db, "StudentDelPDFCat")
    pdf = await _seed_pdf(db, cat.id)
    resp = await client.delete(f"/pdfs/{pdf.id}", headers=auth_headers(student_token))
    assert resp.status_code == 403


# ── GET /bookmarks ────────────────────────────────────────────────────────────

async def test_list_bookmarks_own_only(
    client: AsyncClient, db: AsyncSession,
    admin_user, student_user, student_token: str
):
    cat = await _seed_category(db, "BmListCat")
    q = await _seed_question(db, cat.id, admin_user.id)

    db.add(Bookmark(user_id=student_user.id, question_id=q.id))
    await db.flush()

    resp = await client.get("/bookmarks", headers=auth_headers(student_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["meta"]["total"] == 1
    assert data["items"][0]["question_id"] == q.id


async def test_list_bookmarks_excludes_soft_deleted_question(
    client: AsyncClient, db: AsyncSession,
    admin_user, student_user, student_token: str
):
    cat = await _seed_category(db, "BmSoftDelCat")
    q = await _seed_question(db, cat.id, admin_user.id)
    q.is_deleted = True
    await db.flush()

    db.add(Bookmark(user_id=student_user.id, question_id=q.id))
    await db.flush()

    resp = await client.get("/bookmarks", headers=auth_headers(student_token))
    # Soft-deleted question must not appear in bookmark list
    assert resp.json()["meta"]["total"] == 0


async def test_list_bookmarks_empty_for_new_user(
    client: AsyncClient, student_token: str
):
    resp = await client.get("/bookmarks", headers=auth_headers(student_token))
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] == 0


async def test_list_bookmarks_pagination(
    client: AsyncClient, db: AsyncSession,
    admin_user, student_user, student_token: str
):
    cat = await _seed_category(db, "BmPaginateCat")
    for _ in range(5):
        q = await _seed_question(db, cat.id, admin_user.id)
        db.add(Bookmark(user_id=student_user.id, question_id=q.id))
    await db.flush()

    resp = await client.get(
        "/bookmarks?page=1&per_page=2",
        headers=auth_headers(student_token),
    )
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["meta"]["total"] == 5


async def test_list_bookmarks_requires_auth(client: AsyncClient):
    resp = await client.get("/bookmarks")
    assert resp.status_code in (401, 403)


# ── PATCH /announcements/{id} ─────────────────────────────────────────────────

async def test_patch_announcement_publish_sets_published_at(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token: str
):
    ann = await _seed_announcement(db, admin_user.id, "Draft", is_published=False)
    assert ann.published_at is None

    resp = await client.patch(
        f"/announcements/{ann.id}",
        json={"is_published": True},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_published"] is True
    assert resp.json()["published_at"] is not None


async def test_patch_announcement_edit_body(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token: str
):
    ann = await _seed_announcement(db, admin_user.id, "Original")

    resp = await client.patch(
        f"/announcements/{ann.id}",
        json={"body": "Updated body text."},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["body"] == "Updated body text."


async def test_patch_announcement_not_found(
    client: AsyncClient, admin_token: str
):
    resp = await client.patch(
        "/announcements/99999",
        json={"title": "X"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 404


async def test_patch_announcement_student_forbidden(
    client: AsyncClient, db: AsyncSession, admin_user, student_token: str
):
    ann = await _seed_announcement(db, admin_user.id)
    resp = await client.patch(
        f"/announcements/{ann.id}",
        json={"title": "Hack"},
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 403


# ── DELETE /announcements/{id} ────────────────────────────────────────────────

async def test_delete_announcement_success(
    client: AsyncClient, db: AsyncSession, admin_user, admin_token: str
):
    ann = await _seed_announcement(db, admin_user.id)

    resp = await client.delete(
        f"/announcements/{ann.id}",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert await db.get(Announcement, ann.id) is None


async def test_delete_announcement_not_found(
    client: AsyncClient, admin_token: str
):
    resp = await client.delete(
        "/announcements/99999",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 404


async def test_delete_announcement_student_forbidden(
    client: AsyncClient, db: AsyncSession, admin_user, student_token: str
):
    ann = await _seed_announcement(db, admin_user.id)
    resp = await client.delete(
        f"/announcements/{ann.id}",
        headers=auth_headers(student_token),
    )
    assert resp.status_code == 403