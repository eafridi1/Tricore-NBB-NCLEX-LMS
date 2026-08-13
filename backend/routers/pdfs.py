"""
backend/routers/pdfs.py
=========================
Real implementation of contract.py SECTION 10 — PDFs.
Every path, method, and response_model matches the contract exactly,
with one documented deviation on the download endpoint (see below).

Wire into main.py with:
    from routers import pdfs as pdfs_router
    app.include_router(pdfs_router.router, prefix="/pdfs", tags=["pdfs"])

Install dependencies:
    pip install pypdf reportlab

CONTRACT DEVIATION — GET /pdfs/{pdf_id}/download:
    The contract defines response_model=PDFDownloadResponse, which is a
    JSON payload containing a download_url string. Returning a raw
    storage URL here would let any student strip the token from the
    response and share the URL — bypassing watermarking entirely. The
    task instruction overrides the contract: return actual watermarked
    PDF bytes as a StreamingResponse (application/pdf), not a JSON URL.
    The frontend dev must handle this as a file download (blob response),
    not a JSON parse. This is documented in CONTRACT_STATUS.md under
    a "behavior note" for this endpoint.
"""

from __future__ import annotations

import re
import urllib.request
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import get_current_user, require_admin, require_active_subscription
from models import Category, PDF, User, UserRole
from storage import get_signed_url, R2_CONFIGURED

router = APIRouter()


# ── Request / Response models ──────────────────────────────────────────────
# Copied verbatim from contract.py SECTION 10.
# PDFDownloadResponse is defined for contract shape reference only —
# GET /{pdf_id}/download returns StreamingResponse, not this model.

class PDFOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    category_id: int
    sort_order: int
    is_published: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PDFDownloadResponse(BaseModel):
    """
    Defined here for contract shape reference only. NOT used as the actual
    response model for GET /{pdf_id}/download — see module docstring.
    Kept so /docs still shows the intended contract shape alongside the
    actual streaming endpoint.
    """
    download_url: str
    expires_at: datetime
    filename: str


class PaginationMeta(BaseModel):
    total: int
    page: int
    per_page: int
    pages: int


class PDFListResponse(BaseModel):
    items: list[PDFOut]
    meta: PaginationMeta


class PDFCreateRequest(BaseModel):
    title: str = Field(..., example="Cardiovascular Pharmacology Notes")
    description: Optional[str] = None
    category_id: int
    storage_url: str
    sort_order: int = 0


class PDFUpdateRequest(BaseModel):
    # Partial update — same rationale as videos.py and announcements.py.
    title: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    storage_url: Optional[str] = None
    sort_order: Optional[int] = None
    is_published: Optional[bool] = None


class MessageResponse(BaseModel):
    message: str


# ── Watermark logic ──────────────────────────────────────────────────────────

def _safe_filename(text: str) -> str:
    """
    Strip characters that are unsafe in Content-Disposition filenames.
    Keeps letters, digits, hyphens, underscores, dots.
    """
    return re.sub(r"[^\w\-.]", "_", text)


def _create_watermark_page(
    width: float,
    height: float,
    watermark_text: str,
) -> BytesIO:
    """
    Create a single-page PDF containing only the diagonal watermark text,
    using reportlab. This page is then merged on top of every page of the
    real PDF using pypdf.

    Returns a BytesIO of the watermark-only PDF page.
    """
    from reportlab.lib.colors import Color
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))

    # Semi-transparent light gray — visible enough to be a deterrent,
    # not so dark it makes the underlying text unreadable.
    c.setFillColor(Color(0.6, 0.6, 0.6, alpha=0.35))

    # Diagonal across the page — harder to crop out than a corner stamp.
    c.setFont("Helvetica", 11)
    c.saveState()
    c.translate(width / 2, height / 2)
    c.rotate(45)
    c.drawCentredString(0, 0, watermark_text)
    c.restoreState()

    c.save()
    buf.seek(0)
    return buf


def _apply_watermark(pdf_bytes: bytes, watermark_text: str) -> bytes:
    """
    Apply a diagonal watermark to every page of a PDF.

    Process:
      1. Parse the source PDF with pypdf.
      2. Create a watermark page (reportlab) sized to match each page.
      3. Merge the watermark page over each content page.
      4. Return the merged PDF as bytes.

    If pypdf/reportlab are not installed (shouldn't happen post pip install,
    but defensive), raises ImportError with a clear message rather than a
    cryptic AttributeError mid-request.
    """
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        raise ImportError(
            "pypdf is required for PDF watermarking. "
            "Run: pip install pypdf reportlab"
        )

    reader = PdfReader(BytesIO(pdf_bytes))
    writer = PdfWriter()

    for page in reader.pages:
        # Use the actual page dimensions for the watermark overlay so it
        # scales correctly regardless of paper size (A4, Letter, custom).
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)

        watermark_buf = _create_watermark_page(width, height, watermark_text)
        watermark_reader = PdfReader(watermark_buf)
        watermark_page = watermark_reader.pages[0]

        # merge_page() overlays the watermark on top of the content page.
        # The watermark's semi-transparent fill means the underlying text
        # remains readable through it.
        page.merge_page(watermark_page)
        writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    output.seek(0)
    return output.read()


def _create_dev_pdf(watermark_text: str) -> bytes:
    """
    Dev-mode only: generate a minimal PDF from scratch (no real file
    to fetch from R2) and watermark it. Lets the download endpoint work
    end-to-end in Week 3 without real R2 credentials.

    Week 5: remove this function and always fetch real bytes from R2.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        raise ImportError(
            "reportlab is required. Run: pip install pypdf reportlab"
        )

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, height - 100, "TriCore LMS — Study Material")
    c.setFont("Helvetica", 12)
    c.drawString(72, height - 130, "This is a dev-mode placeholder PDF.")
    c.drawString(72, height - 150, "Real content will be served from R2 in production.")

    c.save()
    pdf_bytes = buf.getvalue()

    return _apply_watermark(pdf_bytes, watermark_text)


def _fetch_and_watermark(storage_url: str, watermark_text: str) -> bytes:
    """
    Production path: fetch the real PDF bytes from the signed R2 URL,
    then apply the watermark.

    Week 3: R2_CONFIGURED is False — falls through to dev mode.
    Week 5: R2_CONFIGURED is True — fetches real bytes.
    """
    if not R2_CONFIGURED:
        # Dev mode — return a dummy watermarked PDF
        return _create_dev_pdf(watermark_text)

    # Production: generate a signed URL (60-min expiry) and fetch the bytes.
    # Using urllib rather than httpx/requests to avoid an extra dependency —
    # this is a single synchronous fetch called inside an async route, which
    # is acceptable since PDF downloads are infrequent (not a hot path) and
    # the fetch is bounded by the file size. If this becomes a bottleneck,
    # wrap it in asyncio.to_thread() or switch to httpx.AsyncClient.
    signed_url = get_signed_url(storage_url, expires_in_seconds=3600)
    try:
        with urllib.request.urlopen(signed_url, timeout=30) as resp:
            pdf_bytes = resp.read()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch PDF from storage: {exc}",
        )

    return _apply_watermark(pdf_bytes, watermark_text)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _is_privileged(user: User) -> bool:
    return user.role in (UserRole.admin, UserRole.reviewer)


def _pdf_to_out(pdf: PDF) -> PDFOut:
    return PDFOut(
        id=pdf.id,
        title=pdf.title,
        description=pdf.description,
        category_id=pdf.category_id,
        sort_order=pdf.sort_order,
        is_published=pdf.is_published,
        created_at=pdf.created_at,
    )


# ── GET /pdfs ─────────────────────────────────────────────────────────────────

@router.get("", response_model=PDFListResponse)
async def list_pdfs(
    category_id: Optional[int] = None,
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_subscription),
):
    # SUBSCRIPTION GUARD — deferred to Slice 7. TODO(slice-7): add active
    # subscription check for student role.

    page = max(1, page)
    per_page = max(1, min(per_page, 100))

    query = select(PDF)

    if not _is_privileged(current_user):
        query = query.where(PDF.is_published == True)  # noqa: E712

    if category_id is not None:
        query = query.where(PDF.category_id == category_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    query = (
        query.order_by(PDF.sort_order.asc(), PDF.id.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    pdfs = result.scalars().all()

    pages = (total + per_page - 1) // per_page if total > 0 else 0

    return PDFListResponse(
        items=[_pdf_to_out(p) for p in pdfs],
        meta=PaginationMeta(total=total, page=page, per_page=per_page, pages=pages),
    )


# ── GET /pdfs/{pdf_id}/download ───────────────────────────────────────────────

@router.get("/{pdf_id}/download")
async def download_pdf(
    pdf_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_active_subscription),
):
    """
    Returns watermarked PDF bytes as a StreamingResponse.

    NOTE: response_model is intentionally omitted here — FastAPI's
    response_model validation applies to JSON responses only, and
    StreamingResponse bypasses it. The contract's PDFDownloadResponse
    model (JSON with download_url) is NOT used — see module docstring
    for the full rationale. The frontend must handle this as a file
    download (fetch with responseType: 'blob', or an <a> tag), not
    a JSON parse.
    """
    pdf = await db.get(PDF, pdf_id)

    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found.")

    if not pdf.is_published and not _is_privileged(current_user):
        # Anti-enumeration: same 404 posture as questions.py and videos.py.
        raise HTTPException(status_code=404, detail="PDF not found.")

    # Build watermark text — PRD F8-1 specifies: student name + email +
    # download timestamp. ISO format for timestamp keeps it unambiguous
    # across timezones (Pakistan, Nigeria, Philippines — all NBB's potential
    # markets — have different local times).
    now = datetime.now(timezone.utc)
    watermark_text = (
        f"{current_user.name} | {current_user.email} | "
        f"{now.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    )

    # Generate watermarked bytes. Never cached — generated fresh on every
    # download request. PRD F8-1: "applied server-side on every download
    # request — not pre-watermarked." Caching would require storing per-user
    # copies in R2 (negating the storage savings of a single source file)
    # and would make the timestamp stale. On-demand is the correct approach.
    try:
        watermarked_bytes = _fetch_and_watermark(pdf.storage_url, watermark_text)
    except HTTPException:
        raise  # re-raise 502 from _fetch_and_watermark cleanly
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate watermarked PDF: {exc}",
        )

    safe_title = _safe_filename(pdf.title)
    filename = f"{safe_title}-{current_user.id}.pdf"

    return StreamingResponse(
        content=iter([watermarked_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            # Content-Length helps browsers show a real progress bar
            "Content-Length": str(len(watermarked_bytes)),
        },
    )


# ── POST /pdfs ────────────────────────────────────────────────────────────────

@router.post("", response_model=PDFOut, status_code=201)
async def create_pdf(
    data: PDFCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if data.category_id is not None:
        category = await db.get(Category, data.category_id)
        if not category:
            raise HTTPException(
                status_code=400,
                detail=f"category_id {data.category_id} does not exist.",
            )

    pdf = PDF(
        title=data.title,
        description=data.description,
        category_id=data.category_id,
        storage_url=data.storage_url,
        sort_order=data.sort_order,
        is_published=False,
    )
    db.add(pdf)
    await db.commit()
    await db.refresh(pdf)
    return _pdf_to_out(pdf)


# ── PATCH /pdfs/{pdf_id} ──────────────────────────────────────────────────────

@router.patch("/{pdf_id}", response_model=PDFOut)
async def update_pdf(
    pdf_id: int,
    data: PDFUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    pdf = await db.get(PDF, pdf_id)
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found.")

    if data.category_id is not None:
        category = await db.get(Category, data.category_id)
        if not category:
            raise HTTPException(
                status_code=400,
                detail=f"category_id {data.category_id} does not exist.",
            )

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(pdf, field, value)

    await db.commit()
    await db.refresh(pdf)
    return _pdf_to_out(pdf)


# ── DELETE /pdfs/{pdf_id} ─────────────────────────────────────────────────────

@router.delete("/{pdf_id}", response_model=MessageResponse)
async def delete_pdf(
    pdf_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    pdf = await db.get(PDF, pdf_id)
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found.")

    # Same storage orphan note as videos.py — DB row deleted, R2 object
    # stays until manual cleanup or a Week 5+ maintenance script.
    storage_url = pdf.storage_url
    await db.delete(pdf)
    await db.commit()

    return MessageResponse(
        message=f"PDF deleted. Storage object '{storage_url}' must be "
                f"removed manually from R2 until automated cleanup is implemented."
    )