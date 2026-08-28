"""Photographs on menu items and ingredients.

What is being protected:

  * an upload is never stored as sent. It is decoded, rotated, capped and
    re-encoded, so the bytes a browser later receives were produced by Pillow
    from pixels and were never authored by the uploader;
  * the served image is cacheable forever and answers a revalidation with 304,
    which is what keeps a forty-row stock table from costing forty image
    requests on every visit;
  * one ingredient photograph reaches every screen that names the ingredient
    (the stock position, a purchase order line, a supplier's catalogue) through
    the response itself, not through a per-row lookup the UI would have to do;
  * uploading requires an admin; fetching requires nothing, because an `<img>`
    tag cannot carry a token.

These run on SQLite; the bytea column is a BLOB there. The end-to-end check is
the deployed API.
"""

from __future__ import annotations

import io
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Ingredient
from app.models.location import Location
from app.models.menu import Category
from app.models.procurement import Supplier
from app.models.tenant import Tenant
from app.models.user import User
from app.services import purchase_order_service, stock_service, supplier_service
from app.services.media_service import MAX_UPLOAD_BYTES

pytestmark = pytest.mark.asyncio


def _png(width: int = 1600, height: int = 1200, mode: str = "RGB") -> bytes:
    img = Image.new(mode, (width, height), (200, 120, 40) if mode == "RGB" else (200, 120, 40, 0))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


async def _upload(client, token: str | None, data: bytes, filename: str = "photo.png"):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return await client.post(
        "/api/v1/media/images",
        files={"file": (filename, data, "image/png")},
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Upload + delivery
# ---------------------------------------------------------------------------


async def test_upload_is_normalised_and_served_cacheable(client, admin_token: str, tenant: Tenant):
    """1600x1200 PNG in, 1200x900 progressive JPEG out, cached forever."""
    resp = await _upload(client, admin_token, _png(1600, 1200))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["url"] == f"/api/v1/media/{body['id']}"
    assert body["content_type"] == "image/jpeg"
    assert (body["width"], body["height"]) == (1200, 900), "long side must be capped at 1200"

    got = await client.get(body["url"])
    assert got.status_code == 200
    assert got.headers["content-type"].startswith("image/jpeg")
    assert "immutable" in got.headers["cache-control"]
    assert got.headers.get("etag")

    served = Image.open(io.BytesIO(got.content))
    assert served.format == "JPEG"
    assert served.size == (1200, 900)

    # A browser holding the image revalidates with the ETag and gets no body.
    again = await client.get(body["url"], headers={"If-None-Match": got.headers["etag"]})
    assert again.status_code == 304
    assert again.content == b""


async def test_small_images_are_not_upscaled(client, admin_token: str):
    resp = await _upload(client, admin_token, _png(400, 300))
    assert resp.status_code == 201, resp.text
    assert (resp.json()["width"], resp.json()["height"]) == (400, 300)


async def test_transparency_is_flattened_onto_white(client, admin_token: str):
    """A PNG logo with a clear background must not come back on black."""
    resp = await _upload(client, admin_token, _png(200, 200, mode="RGBA"))
    assert resp.status_code == 201, resp.text
    got = await client.get(resp.json()["url"])
    px = Image.open(io.BytesIO(got.content)).getpixel((100, 100))
    assert all(c > 240 for c in px), f"transparent area rendered as {px}, expected white"


async def test_a_non_image_is_refused(client, admin_token: str):
    resp = await _upload(client, admin_token, b"this is not an image at all", filename="x.png")
    assert resp.status_code == 400, resp.text
    assert "not a usable image" in resp.json()["detail"]


async def test_oversize_upload_is_refused_before_decoding(client, admin_token: str):
    """Over the cap is a 413 whatever the bytes are; the size check comes first."""
    resp = await _upload(client, admin_token, b"\0" * (MAX_UPLOAD_BYTES + 1))
    assert resp.status_code == 413, resp.text


async def test_upload_requires_an_admin(client, cashier_token: str):
    anonymous = await _upload(client, None, _png(100, 100))
    assert anonymous.status_code == 401

    cashier = await _upload(client, cashier_token, _png(100, 100))
    assert cashier.status_code == 403


async def test_fetching_an_unknown_image_is_404(client):
    resp = await client.get(f"/api/v1/media/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_head_is_answered_with_the_same_headers_and_no_body(client, admin_token: str):
    """A link checker or CDN probing with HEAD must not get 405."""
    up = await _upload(client, admin_token, _png(120, 90))
    url = up.json()["url"]
    head = await client.head(url)
    assert head.status_code == 200, head.text
    assert head.headers["content-type"].startswith("image/jpeg")
    assert "immutable" in head.headers["cache-control"]
    assert head.headers.get("etag")
    assert head.content == b""
    assert int(head.headers["content-length"]) == up.json()["size_bytes"]


async def test_fetching_needs_no_token(client, admin_token: str):
    """The URL goes into an <img src>, which sends no Authorization header."""
    up = await _upload(client, admin_token, _png(120, 90))
    got = await client.get(up.json()["url"])
    assert got.status_code == 200


# ---------------------------------------------------------------------------
# The URL on the records
# ---------------------------------------------------------------------------


async def test_menu_item_accepts_and_reports_an_uploaded_image(
    client, db: AsyncSession, tenant: Tenant, admin_token: str
):
    cat = Category(tenant_id=tenant.id, name="Pastries", display_order=1, is_active=True)
    db.add(cat)
    await db.commit()

    up = await _upload(client, admin_token, _png(800, 600))
    url = up.json()["url"]

    headers = {"Authorization": f"Bearer {admin_token}"}
    created = await client.post(
        "/api/v1/menu/items",
        json={"name": "Butter Croissant", "price": 900, "category_id": str(cat.id), "image_url": url},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["image_url"] == url

    full = await client.get("/api/v1/menu/full", headers=headers)
    items = [i for c in full.json()["categories"] for i in c["items"]]
    assert items[0]["image_url"] == url, "the POS grid reads /menu/full; the URL must reach it"

    cleared = await client.patch(
        f"/api/v1/menu/items/{created.json()['id']}",
        json={"image_url": None},
        headers=headers,
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["image_url"] is None


async def test_ingredient_accepts_reports_and_clears_an_image(client, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    up = await _upload(client, admin_token, _png(800, 600))
    url = up.json()["url"]

    created = await client.post(
        "/api/v1/inventory/ingredients",
        json={"name": "Flour", "unit": "kg", "image_url": url},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["image_url"] == url

    listed = await client.get("/api/v1/inventory/ingredients", headers=headers)
    assert listed.json()[0]["image_url"] == url

    cleared = await client.patch(
        f"/api/v1/inventory/ingredients/{created.json()['id']}",
        json={"image_url": None},
        headers=headers,
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["image_url"] is None


# ---------------------------------------------------------------------------
# One photograph, every screen
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def site(db: AsyncSession, tenant: Tenant) -> Location:
    loc = Location(
        tenant_id=tenant.id, name="Production", code="PROD",
        location_type="production", is_default=True,
    )
    db.add(loc)
    await db.flush()
    return loc


@pytest_asyncio.fixture
async def flour(db: AsyncSession, tenant: Tenant) -> Ingredient:
    ing = Ingredient(
        tenant_id=tenant.id, name="Flour", unit="kg",
        cost_per_unit=Decimal("400"), image_url="/api/v1/media/flour-photo",
    )
    db.add(ing)
    await db.flush()
    return ing


@pytest_asyncio.fixture
async def supplier(db: AsyncSession, tenant: Tenant) -> Supplier:
    return await supplier_service.create_supplier(
        db, tenant.id, {"name": "Al Maya Trading", "code": "almaya", "lead_time_days": 2},
    )


async def test_stock_position_carries_the_ingredient_photo(
    client, db: AsyncSession, tenant: Tenant, site: Location, flour: Ingredient,
    admin_user: User, admin_token: str,
):
    await stock_service.move_stock(
        db, tenant_id=tenant.id, ingredient_id=flour.id, quantity_delta=Decimal("25"),
        transaction_type="adjustment", location_id=site.id, performed_by=admin_user.id,
        notes="opening stock",
    )
    await db.commit()

    resp = await client.get(
        "/api/v1/locations/stock/position", headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    row = next(r for r in resp.json() if r["ingredient_id"] == str(flour.id))
    assert row["ingredient_image_url"] == "/api/v1/media/flour-photo"


async def test_supplier_catalogue_and_purchase_order_lines_carry_the_photo(
    client, db: AsyncSession, tenant: Tenant, site: Location, flour: Ingredient,
    supplier: Supplier, admin_token: str,
):
    await supplier_service.upsert_supplier_item(
        db, tenant.id, supplier.id, {"ingredient_id": flour.id, "last_price_minor": Decimal("380")},
    )
    await purchase_order_service.create_purchase_order(
        db, tenant_id=tenant.id, supplier_id=supplier.id, location_id=site.id,
        lines=[{"ingredient_id": flour.id, "quantity_ordered": Decimal("10")}], tax_bps=500,
    )
    await db.commit()

    headers = {"Authorization": f"Bearer {admin_token}"}
    catalogue = await client.get(
        "/api/v1/procurement/catalogue", params={"supplier_id": str(supplier.id)}, headers=headers,
    )
    assert catalogue.status_code == 200, catalogue.text
    assert catalogue.json()[0]["ingredient_image_url"] == "/api/v1/media/flour-photo"

    orders = await client.get("/api/v1/procurement/purchase-orders", headers=headers)
    assert orders.status_code == 200, orders.text
    assert orders.json()[0]["items"][0]["ingredient_image_url"] == "/api/v1/media/flour-photo"


async def test_an_ingredient_without_a_photo_reports_null_everywhere(
    client, db: AsyncSession, tenant: Tenant, site: Location, admin_user: User, admin_token: str,
):
    """The default. Every existing ingredient has no photo and must keep working."""
    plain = Ingredient(tenant_id=tenant.id, name="Salt", unit="kg", cost_per_unit=Decimal("150"))
    db.add(plain)
    await db.flush()
    await stock_service.move_stock(
        db, tenant_id=tenant.id, ingredient_id=plain.id, quantity_delta=Decimal("5"),
        transaction_type="adjustment", location_id=site.id, performed_by=admin_user.id,
        notes="opening stock",
    )
    await db.commit()

    resp = await client.get(
        "/api/v1/locations/stock/position", headers={"Authorization": f"Bearer {admin_token}"},
    )
    row = next(r for r in resp.json() if r["ingredient_id"] == str(plain.id))
    assert row["ingredient_image_url"] is None
