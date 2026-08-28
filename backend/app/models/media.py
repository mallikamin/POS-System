"""Uploaded images, stored in the database and served by the API.

Why the bytes live in Postgres rather than on disk:

  * the production backend container runs with a read-only root filesystem
    and only `/app/logs` and a 64 MB `/tmp` are writable, so a disk store
    means a new bind mount in compose and a new directory the deploy script
    must create and chown;
  * nginx on that box is shared with two other businesses' hostnames, and a
    new static `location` means recreating the container, which blips every
    one of them;
  * `pg_dump` is the one backup that is actually taken before every risky
    change. A photo in the database is in that backup; a photo on disk is not.

Images are normalised at upload (EXIF-rotated, capped at 1200 px on the long
side, re-encoded as JPEG), so a row is ~50-150 KB, not a 6 MB phone original.
Rows are never listed, only fetched one at a time by id, so the payload column
is loaded on demand and never rides along with a query that did not ask for it.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID as Uuid
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.database import Base
from app.models.base import BaseMixin


class MediaFile(BaseMixin, Base):
    __tablename__ = "media_files"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )

    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    data: Mapped[bytes] = deferred(mapped_column(LargeBinary, nullable=False))
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    # Content hash of the stored (normalised) bytes. Doubles as the ETag, so a
    # browser that already holds the image is answered with 304 and no body.
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
