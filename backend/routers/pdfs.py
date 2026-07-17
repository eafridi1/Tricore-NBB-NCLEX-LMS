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
from dependencies import get_current_user, require_admin
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


def _create_watermark_page(width: float, height: float) -> BytesIO:
    """
    Create a single-page PDF containing the NBB logo centered on the page,
    at very low opacity — matching the subtle look of the brand letterhead.

    The logo PNG (backend/assets/nbb_watermark.png) must exist. It has a
    transparent background and the logo in NBB navy (#0B2540).

    Opacity is controlled by drawing the image at low alpha via reportlab's
    ImageReader + canvas.drawImage with mask='auto' to respect transparency,
    then setting the fill alpha. The effective visual opacity is ~8% —
    barely visible, consistent with the reference image provided.

    # TO RE-ENABLE TEXT WATERMARK (student identity tracing):
    # Uncomment the block below inside this function after drawing the logo:
    #
    #   c.saveState()
    #   c.setFillColor(Color(0.4, 0.4, 0.4, alpha=0.15))
    #   c.setFont("Helvetica", 9)
    #   c.translate(width / 2, height / 2)
    #   c.rotate(30)
    #   c.drawCentredString(0, -40, watermark_text)
    #   c.restoreState()
    #
    # watermark_text should be passed as a parameter:
    #   def _create_watermark_page(width, height, watermark_text=""):
    """
    from reportlab.lib.colors import Color
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    logo_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),  # backend/
        "assets",
        "nbb_watermark.png",
    )

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))

    if os.path.exists(logo_path):
        # Size the logo to 38% of the page width — large enough to be
        # recognisable as the NBB mark, small enough not to obscure content.
        logo_w = width * 0.38
        # Maintain aspect ratio — the extracted logo is 1083×1411 px (portrait)
        logo_h = logo_w * (1411 / 1083)

        # Center on the page
        x = (width - logo_w) / 2
        y = (height - logo_h) / 2

        # The logo PNG is already very light steel-blue (#EAF1F9) — this IS
        # the approved watermark color from the brand team. Drawing at full
        # opacity (1.0) produces the subtle look in the reference image.
        # If you want it even more subtle, lower this value (e.g. 0.7).
        LOGO_OPACITY = 1.0
        c.saveState()
        c.setFillAlpha(LOGO_OPACITY)
        c.setStrokeAlpha(LOGO_OPACITY)
        c.drawImage(
            ImageReader(logo_path),
            x, y,
            width=logo_w,
            height=logo_h,
            mask='auto',      # respects the PNG transparency channel
            preserveAspectRatio=True,
        )
        c.restoreState()
    else:
        # Fallback if the logo file is missing — silent, don't crash the
        # download. The PDF is returned without a watermark rather than
        # erroring with a 500. Worth adding a log warning here once
        # structured logging is wired in Week 5.
        pass

    c.save()
    buf.seek(0)
    return buf


def _apply_watermark(pdf_bytes: bytes) -> bytes:
    """
    Apply the NBB logo watermark to every page of a PDF.

    Signature change from the old version: `watermark_text` parameter
    removed since the logo watermark doesn't use text. The student identity
    text (name/email/timestamp) is preserved as commented-out code inside
    _create_watermark_page() for easy re-enabling later.
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
        width  = float(page.mediabox.width)
        height = float(page.mediabox.height)

        watermark_buf    = _create_watermark_page(width, height)
        watermark_reader = PdfReader(watermark_buf)
        watermark_page   = watermark_reader.pages[0]

        page.merge_page(watermark_page)
        writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    output.seek(0)
    return output.read()


def _create_dev_pdf() -> bytes:
    """
    Dev-mode only: generate a minimal PDF from scratch and watermark it.
    Signature change: watermark_text removed (logo watermark has no text).
    Week 5: remove this and always fetch real bytes from R2.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as rl_canvas
    except ImportError:
        raise ImportError(
            "reportlab is required. Run: pip install pypdf reportlab"
        )

    buf = BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, height - 100, "TriCore LMS — Study Material")
    c.setFont("Helvetica", 12)
    c.drawString(72, height - 130, "This is a dev-mode placeholder PDF.")
    c.drawString(72, height - 150, "Real content will be served from R2 in production.")

    c.save()
    pdf_bytes = buf.getvalue()

    return _apply_watermark(pdf_bytes)


def _fetch_and_watermark(storage_url: str) -> bytes:
    """
    Signature change: watermark_text removed.
    Week 3: dev mode — returns dummy watermarked PDF.
    Week 5: R2_CONFIGURED=True — fetches real bytes from R2.
    """
    if not R2_CONFIGURED:
        return _create_dev_pdf()

    signed_url = get_signed_url(storage_url, expires_in_seconds=3600)
    try:
        with urllib.request.urlopen(signed_url, timeout=30) as resp:
            pdf_bytes = resp.read()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch PDF from storage: {exc}",
        )

    return _apply_watermark(pdf_bytes)


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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
        raise HTTPException(status_code=404, detail="PDF not found.")

    # Generate watermarked bytes — logo watermark, no student text for now.
    # To re-enable student identity text (name/email/timestamp), see the
    # commented-out block inside _create_watermark_page().
    try:
        watermarked_bytes = _fetch_and_watermark(pdf.storage_url)
    except HTTPException:
        raise
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


    # METHODOLIGY:
'''
    Student request
      │
      ▼
download_pdf() route
  │  1. Auth check (get_current_user)
  │  2. Fetch PDF row from DB (title, storage_url, is_published)
  │  3. Access check (student can't see unpublished)
  │  4. Build filename: "Test_PDF-5.pdf"
  │  5. Call _fetch_and_watermark(pdf.storage_url)
      │
      ▼
_fetch_and_watermark(storage_url)
  │  Check: is R2_CONFIGURED in .env?
  │  ├── NO (dev mode) → call _create_dev_pdf()
  │  │       Generates a blank A4 PDF using reportlab from scratch
  │  │       Then calls _apply_watermark(pdf_bytes)
  │  │
  │  └── YES (production) → fetch real bytes from R2 signed URL
  │          Then calls _apply_watermark(pdf_bytes)
      │
      ▼
_apply_watermark(pdf_bytes)
  │  1. Opens PDF bytes with pypdf PdfReader
  │  2. Creates a PdfWriter (empty)
  │  3. Loops over every page:
  │       a. Gets page dimensions (width × height)
  │       b. Calls _create_watermark_page(width, height)
  │       c. Merges watermark page ON TOP of content page
  │       d. Adds merged page to writer
  │  4. Returns merged PDF as bytes
      │
      ▼
_create_watermark_page(width, height)
  │  1. Creates a blank PDF page (same size as the content page)
  │  2. Loads nbb_logo.png from backend/assets/
  │  3. Calculates: logo_w = page_width × 38%, maintain aspect ratio
  │  4. Centers the logo: x = (page_w - logo_w) / 2
  │  5. Draws the logo at LOGO_OPACITY=1.0
  │     (logo is already very light so full opacity = subtle look)
  │  6. Returns the watermark-only page as BytesIO
      │
      ▼
Back in download_pdf()
  │  StreamingResponse(
  │    content = watermarked_bytes,
  │    media_type = "application/pdf",
  │    Content-Disposition = 'attachment; filename="Test_PDF-5.pdf"'
  │    Content-Length = <byte count>
  │  )
      │
      ▼
Browser downloads the file

'''