"""Image uploads: validate, normalise, store, fetch.

Every upload is decoded and re-encoded here, whatever the client sent. That is
the security boundary as much as the size control: the bytes that reach the
database are ones Pillow produced from pixels, never the uploaded file itself,
so a crafted file that is "an image" only by extension is rejected at
`Image.open`, and nothing a browser later receives from `/media/{id}` was
authored by an uploader.

`MAX_UPLOAD_BYTES` matches nginx's `client_max_body_size 5M` in
`nginx.demo.conf`. A larger file is refused by nginx before it gets here; the
same limit is enforced here so the API behaves identically without nginx in
front of it (tests, local dev).
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import uuid

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.models.media import MediaFile

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_SIDE = 1200
JPEG_QUALITY = 82
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}

# Pillow refuses to decode anything above this many pixels, so a tiny file that
# claims to be 30000x30000 cannot exhaust memory during decode. 50 MP is well
# above any phone camera and far above anything a menu card needs.
Image.MAX_IMAGE_PIXELS = 50_000_000


class InvalidImage(ValueError):
    """The upload is not an image this system accepts."""


class ImageTooLarge(ValueError):
    """The upload exceeds MAX_UPLOAD_BYTES."""


def normalise_image(data: bytes) -> tuple[bytes, int, int]:
    """Decode, orient, flatten, cap, re-encode. Returns (jpeg_bytes, width, height).

    Synchronous and CPU-bound; call it through `asyncio.to_thread` from the
    request path so a large decode does not stall the event loop.
    """
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in ALLOWED_FORMATS:
            raise InvalidImage(f"unsupported image format: {img.format or 'unknown'}")
        img.load()
    except Image.DecompressionBombError as exc:
        raise InvalidImage("image dimensions are too large") from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise InvalidImage("file is not a readable image") from exc

    # Phone photos carry their rotation in EXIF; without this a portrait shot
    # lands on the card sideways.
    img = ImageOps.exif_transpose(img) or img

    # Flatten transparency onto white rather than onto black, which is what a
    # bare RGB conversion would do to a PNG logo with a clear background.
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.getchannel("A"))
        img = flat
    else:
        img = img.convert("RGB")

    img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    return out.getvalue(), img.width, img.height


def public_url(media_id: uuid.UUID) -> str:
    """The path a browser fetches. Relative, so it works on every hostname."""
    return f"/api/v1/media/{media_id}"


async def store_image(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: bytes,
    original_filename: str | None = None,
) -> MediaFile:
    if not data:
        raise InvalidImage("empty upload")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageTooLarge(f"upload exceeds {MAX_UPLOAD_BYTES} bytes")

    jpeg, width, height = await asyncio.to_thread(normalise_image, data)

    media = MediaFile(
        tenant_id=tenant_id,
        content_type="image/jpeg",
        data=jpeg,
        size_bytes=len(jpeg),
        width=width,
        height=height,
        sha256=hashlib.sha256(jpeg).hexdigest(),
        original_filename=(original_filename or "")[:255] or None,
    )
    db.add(media)
    await db.flush()
    return media


class InvalidDocument(ValueError):
    """The upload is not a document this system accepts."""


# A supplier or landlord sends a PDF; a phone sends a photograph of a paper
# bill. Both are invoices, so both are accepted, and nothing else is.
PDF_MAGIC = b"%PDF-"


async def store_document(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    data: bytes,
    original_filename: str | None = None,
) -> MediaFile:
    """Store an invoice: a PDF as sent, an image normalised as usual.

    Added for Martin's M10 (expense invoices). The split matters:

    * **An image goes through `normalise_image`**, exactly like a menu
      photograph, so a 6 MB phone original becomes a ~100 KB JPEG and the bytes
      that reach the database are ones Pillow produced from pixels.
    * **A PDF is stored byte-for-byte**, because re-encoding it would destroy
      the document, and it is only ever served back with an explicit
      `application/pdf` content type and never rendered as HTML.

    🔴 The type is decided by the CONTENT, not by the filename or the browser's
    `Content-Type` header. Both are attacker-controlled; the magic bytes are
    not. Anything that is neither a PDF nor a decodable image is refused.
    """
    if not data:
        raise InvalidDocument("empty upload")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageTooLarge(f"upload exceeds {MAX_UPLOAD_BYTES} bytes")

    if data[: len(PDF_MAGIC)] == PDF_MAGIC:
        media = MediaFile(
            tenant_id=tenant_id,
            content_type="application/pdf",
            data=data,
            size_bytes=len(data),
            # A PDF has pages, not pixels. Zero rather than a guess, and the
            # columns are NOT NULL so they cannot simply be left out.
            width=0,
            height=0,
            sha256=hashlib.sha256(data).hexdigest(),
            original_filename=(original_filename or "")[:255] or None,
        )
        db.add(media)
        await db.flush()
        return media

    try:
        return await store_image(db, tenant_id, data, original_filename)
    except InvalidImage as exc:
        raise InvalidDocument(
            f"that file is neither a PDF nor a usable image ({exc})"
        ) from exc


async def get_media_bytes(db: AsyncSession, media_id: uuid.UUID) -> MediaFile | None:
    """Fetch one file with its bytes, for a caller that has already authorised it.

    Same query as `get_media`; named apart so a reader can see at the call site
    that the expense route is not reusing the deliberately unauthenticated
    image path below.
    """
    result = await db.execute(
        select(MediaFile).options(undefer(MediaFile.data)).where(MediaFile.id == media_id)
    )
    return result.scalar_one_or_none()


async def get_media(db: AsyncSession, media_id: uuid.UUID) -> MediaFile | None:
    """Fetch one image with its bytes.

    Deliberately not tenant-scoped: an `<img>` tag cannot send a bearer token,
    so the URL has to be fetchable without one. The id is a random UUID, which
    is the same unguessability a signed CDN URL provides, and the content is a
    menu or ingredient photograph that the storefront shows the public anyway.
    """
    result = await db.execute(
        select(MediaFile).options(undefer(MediaFile.data)).where(MediaFile.id == media_id)
    )
    return result.scalar_one_or_none()
