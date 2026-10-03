"""Danny's D-99: visit loyalty endpoints. Thin; the rules live in loyalty_service.

Staff routes need a login. The two public routes back the page a customer
reaches by scanning a bill's QR: they expose only the restaurant's name, the
reward wording and the scanning customer's own progress, never another
customer's details.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.database import get_db
from app.integrations import google_wallet
from app.models.user import User
from app.services import loyalty_service
from app.services.loyalty_service import LoyaltyError, Progress

router = APIRouter(prefix="/loyalty", tags=["loyalty"])
public_router = APIRouter(prefix="/public/loyalty", tags=["loyalty-public"])


class ProgressOut(BaseModel):
    customer_id: uuid.UUID
    customer_name: str
    phone: str
    total_visits: int
    visits_required: int
    toward_next: int
    rewards_earned: int
    rewards_redeemed: int
    rewards_available: int
    reward_label: str
    last_visit: str | None


def _out(p: Progress) -> ProgressOut:
    return ProgressOut(**p.__dict__)


def _mask(phone: str) -> str:
    return phone[:4] + "*" * max(len(phone) - 7, 0) + phone[-3:] if len(phone) > 7 else phone


def _bad(exc: LoyaltyError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# --- Staff -------------------------------------------------------------------

@router.get("/customers/{phone}", response_model=ProgressOut | None)
async def customer_progress(
    phone: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    p = await loyalty_service.progress_by_phone(db, user.tenant_id, phone)
    return _out(p) if p else None


@router.get("/orders/{order_id}")
async def order_loyalty(
    order_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    try:
        return await loyalty_service.order_status(db, user.tenant_id, order_id)
    except LoyaltyError as exc:
        raise _bad(exc) from exc


@router.post("/orders/{order_id}/redeem", response_model=ProgressOut)
async def redeem_reward(
    order_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    try:
        return _out(await loyalty_service.redeem(db, user.tenant_id, user.id, order_id))
    except LoyaltyError as exc:
        raise _bad(exc) from exc


@router.get("/display")
async def counter_display(
    idle: bool = False,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> dict | None:
    # `idle=1`: also return the rule when no bill is waiting (D-106 counter screen).
    return await loyalty_service.display_current(db, user.tenant_id, with_idle=idle)


@router.get("/members", response_model=list[ProgressOut],
            dependencies=[Depends(require_role("admin"))])
async def list_members(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return [_out(p) for p in await loyalty_service.members(db, user.tenant_id)]


# --- Public (the customer's phone, after scanning) ----------------------------

class ClaimIn(BaseModel):
    phone: str = Field(..., min_length=7, max_length=20)
    name: str | None = Field(None, max_length=100)
    consent: bool


@public_router.get("/{code}")
async def public_claim_info(code: str, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        info = await loyalty_service.claim_info(db, code)
    except LoyaltyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": info.status, "restaurant_name": info.restaurant_name,
            "visits_required": info.visits_required, "reward_label": info.reward_label,
            "order_number": info.order_number, "tenant_slug": info.tenant_slug,
            "google_wallet": google_wallet.available_for(info.tenant_slug)}


@public_router.post("/{code}")
async def public_claim(code: str, body: ClaimIn, db: AsyncSession = Depends(get_db)) -> dict:
    if not body.consent:
        raise HTTPException(status_code=400, detail="Please tick the box to join.")
    try:
        result, p = await loyalty_service.claim(db, code, body.phone, body.name)
    except LoyaltyError as exc:
        raise _bad(exc) from exc
    # Only this customer's own counts, and the phone masked.
    return {"result": result, "phone": _mask(p.phone), "total_visits": p.total_visits,
            "toward_next": p.toward_next, "visits_required": p.visits_required,
            "rewards_available": p.rewards_available, "reward_label": p.reward_label}


class WalletIn(BaseModel):
    phone: str = Field(..., min_length=7, max_length=20)


@public_router.post("/{code}/google-wallet")
async def public_google_wallet(code: str, body: WalletIn, db: AsyncSession = Depends(get_db)) -> dict:
    """The "Add to Google Wallet" link, for the guest whose number is on this bill."""
    try:
        return {"url": await loyalty_service.wallet_link(db, code, body.phone)}
    except LoyaltyError as exc:
        raise _bad(exc) from exc
