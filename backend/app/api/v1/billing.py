"""Billing endpoints: Stripe checkout, portal, and webhooks."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.billing import BillingStatusRead, CheckoutRequest, CheckoutResponse, PortalResponse
from app.services.billing import BillingService

router = APIRouter()


@router.get("/status", response_model=BillingStatusRead)
def billing_status(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> BillingStatusRead:
    """Return billing capabilities and subscription state for the signed-in user."""
    return BillingService(db).status(user.id)


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(
    data: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CheckoutResponse:
    """Start a Stripe Checkout session for a paid plan."""
    url = BillingService(db).create_checkout_session(
        user.id, plan=data.plan, billing_period=data.billing_period
    )
    return CheckoutResponse(url=url)


@router.post("/portal", response_model=PortalResponse)
def create_portal(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> PortalResponse:
    """Open the Stripe customer portal to manage an existing subscription."""
    url = BillingService(db).create_portal_session(user.id)
    return PortalResponse(url=url)


@router.post("/webhook", status_code=204)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> None:
    """Stripe webhook receiver (unsigned; verified via Stripe-Signature)."""
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    BillingService(db).handle_webhook(payload, signature)
