"""Wire shape for an uploaded image."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class MediaUploadResponse(BaseModel):
    id: uuid.UUID
    # Relative path, ready to be written into `image_url` as-is.
    url: str
    content_type: str
    size_bytes: int
    width: int
    height: int
