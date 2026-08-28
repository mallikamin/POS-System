"""Image upload and delivery.

POST /media/images   admin only, multipart `file`, returns the URL to store
GET  /media/{id}     public, immutable, ETag-aware (see media_service.get_media
                     for why it carries no auth)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.database import get_db
from app.models.user import User
from app.schemas.media import MediaUploadResponse
from app.services import media_service
from app.services.media_service import ImageTooLarge, InvalidImage, MAX_UPLOAD_BYTES

router = APIRouter(prefix="/media", tags=["media"])

_admin_dep = require_role("admin")

# A year, and `immutable`: the bytes behind an id never change (a new upload
# is a new id), so the browser need never revalidate. This is what makes a
# stock table with forty thumbnails cost forty requests once, not per visit.
_CACHE_FOREVER = "public, max-age=31536000, immutable"


@router.post(
    "/images",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(_admin_dep),
    db: AsyncSession = Depends(get_db),
) -> MediaUploadResponse:
    # Read one byte past the cap so an oversize body is recognised without
    # first pulling all of it into memory.
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image must be {MAX_UPLOAD_BYTES // (1024 * 1024)} MB or smaller.",
        )
    try:
        media = await media_service.store_image(
            db, current_user.tenant_id, data, original_filename=file.filename
        )
    except ImageTooLarge:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image must be {MAX_UPLOAD_BYTES // (1024 * 1024)} MB or smaller.",
        )
    except InvalidImage as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"That file is not a usable image ({exc}). Use a JPEG, PNG, WebP or GIF.",
        )
    await db.commit()
    return MediaUploadResponse(
        id=media.id,
        url=media_service.public_url(media.id),
        content_type=media.content_type,
        size_bytes=media.size_bytes,
        width=media.width,
        height=media.height,
    )


# HEAD is accepted alongside GET: FastAPI does not add it for you, and a
# link checker or CDN probing the URL with HEAD got a 405 on the first
# production deploy. Same headers, no body.
@router.api_route("/{media_id}", methods=["GET", "HEAD"], include_in_schema=False)
async def get_image(
    media_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    media = await media_service.get_media(db, media_id)
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    etag = f'"{media.sha256}"'
    headers = {"Cache-Control": _CACHE_FOREVER, "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    if request.method == "HEAD":
        return Response(
            status_code=status.HTTP_200_OK,
            media_type=media.content_type,
            headers={**headers, "Content-Length": str(media.size_bytes)},
        )
    return Response(content=media.data, media_type=media.content_type, headers=headers)
