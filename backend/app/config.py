import sys
from decimal import Decimal

from pydantic_settings import BaseSettings

_INSECURE_DEFAULTS = {"CHANGE-ME-IN-PRODUCTION", "dev-secret-key-change-in-production"}


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Security
    SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://pos_user:pos_pass@localhost:5432/pos_db"

    # Redis
    REDIS_URL: str = "redis://:pos_redis_dev_secret@localhost:6379/0"

    # CORS — stored as comma-separated string, parsed via property
    CORS_ORIGINS: str = (
        "http://localhost:3000,http://localhost:5173,http://localhost:8090"
    )

    # JWT Token lifetimes
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours for a POS shift
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Transactional email (order confirmations).
    # Two transports, chosen by configuration:
    #
    #   BREVO_API_KEY set  -> Brevo's HTTPS API. This is the one production
    #     uses: the DigitalOcean droplet cannot reach ANY outbound SMTP port
    #     (25/465/587 time out, 2525 resets) and Mailjet's API TLS-resets from
    #     that box, all measured from the droplet on 2026-07-29 (OI-55).
    #     api.brevo.com handshakes fine from the same box -- measured, not
    #     assumed.
    #
    #   SMTP_* set (and no BREVO_API_KEY) -> plain SMTP, kept for any future
    #     host whose egress permits mail.
    #
    # Unset means email is disabled and orders still work.
    BREVO_API_KEY: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_STARTTLS: bool = True
    SMTP_SSL: bool = False
    EMAIL_FROM: str = ""
    EMAIL_FROM_NAME: str = ""
    # Where a customer's reply actually lands.
    #
    # This matters more than it looks. Mail is SENT through a relay as
    # orders@<shop domain>, but that address does not necessarily RECEIVE
    # anything -- authenticating a domain for sending says nothing about
    # mailboxes. Without this, a customer who hits reply to ask "can you make
    # it no onion" is writing into a void.
    #
    # Set it to an address the shop genuinely reads. Falls back to EMAIL_FROM.
    EMAIL_REPLY_TO: str = ""
    # Absolute base URL a customer can open to track their order, no trailing
    # slash. The order id is appended. Empty means no link is included.
    ORDER_TRACKING_BASE_URL: str = ""

    # Stripe -- card payments for online orders.
    #
    # The shop charges on ACCEPTANCE, not on placement (the client's own
    # decision, 2026-07-29: "Once accepted"). So the money is AUTHORISED at
    # checkout and only CAPTURED when the shop taps Accept; a rejected order has
    # its authorisation cancelled and the customer is never charged. That is why
    # there is no refund path here -- there is nothing to refund.
    #
    # ⚠️ An authorisation is not indefinite: roughly 5 days on Visa and 7 on
    # Mastercard/Amex for card-not-present. A pre-order cannot be held past that.
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    # Verifies that a webhook genuinely came from Stripe. Without it we would be
    # trusting an unauthenticated POST to tell us an order had been paid.
    STRIPE_WEBHOOK_SECRET: str = ""
    # Where Stripe returns the customer after checkout. The session id is
    # appended by the service.
    STRIPE_SUCCESS_URL: str = ""
    STRIPE_CANCEL_URL: str = ""
    # The currency the Stripe ACCOUNT settles in. A Stripe account has one, and
    # a session created in any other currency is rejected by Stripe with an
    # error the customer sees at the worst possible moment -- on the payment
    # page, having already committed to the order.
    #
    # Checked against the tenant's own configured currency before a session is
    # created, so a tenant misconfigured to PKR fails here, internally and
    # loudly, rather than at Stripe. Not derived from the account by an API call
    # on purpose: that would put a network round trip in front of every
    # checkout, and add a way for checkout to fail that has nothing to do with
    # the payment.
    STRIPE_ACCOUNT_CURRENCY: str = "gbp"

    # QuickBooks Integration
    QB_CLIENT_ID: str = ""
    QB_CLIENT_SECRET: str = ""
    QB_REDIRECT_URI: str = (
        "http://localhost:8090/api/v1/integrations/quickbooks/callback"
    )
    QB_ENVIRONMENT: str = "sandbox"  # sandbox | production

    @property
    def qb_base_url(self) -> str:
        if self.QB_ENVIRONMENT == "production":
            return "https://quickbooks.api.intuit.com"
        return "https://sandbox-quickbooks.api.intuit.com"

    @property
    def qb_auth_url(self) -> str:
        return "https://appcenter.intuit.com/connect/oauth2"

    @property
    def qb_token_url(self) -> str:
        return "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

    @property
    def qb_revoke_url(self) -> str:
        return "https://developer.api.intuit.com/v2/oauth2/tokens/revoke"

    @property
    def qb_configured(self) -> bool:
        return bool(self.QB_CLIENT_ID and self.QB_CLIENT_SECRET)

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in ("production", "prod")

    @property
    def email_configured(self) -> bool:
        """Email is opt-in. Without a transport and a From address, nothing sends.

        A transport is either the Brevo HTTPS API (BREVO_API_KEY) or an SMTP
        host. Deliberately not fatal: an order must never fail because a mail
        server is down or unconfigured. The order is the product; the email is
        a courtesy on top of it.
        """
        return bool((self.BREVO_API_KEY or self.SMTP_HOST) and self.EMAIL_FROM)

    @property
    def stripe_configured(self) -> bool:
        """Card payment is opt-in, exactly like email.

        Without a secret key nothing card-related is offered and orders are
        created unpaid, to be settled in cash on handover -- which is how the
        shop already runs. A half-configured Stripe must never let the
        storefront tell a customer they have paid when they have not.
        """
        return bool(self.STRIPE_SECRET_KEY)

    @property
    def stripe_webhook_configured(self) -> bool:
        """Signature verification is not optional once money is real.

        Capture and cancel are driven from the merchant tablet rather than from
        the webhook, so the system is correct without one. The webhook exists to
        reconcile what Stripe believes against what we believe.
        """
        return bool(self.STRIPE_WEBHOOK_SECRET)

    # -----------------------------------------------------------------
    # AI (Anthropic) -- OCR goods receiving and the ordering advisor
    #
    # Both features are OPT-IN and both degrade to nothing useful being lost:
    # OCR falls back to typing the delivery note in by hand, and the ordering
    # suggestion still produces its full deterministic plan without any model
    # call at all. Unset means no AI, and every other part of the system works
    # exactly as before.
    #
    # Caps exist so a pathological day cannot produce a surprise invoice. They
    # are per tenant per UTC day, counted in the `ai_usage_log` table, and they
    # degrade gracefully: the caller is told the cap is reached, never crashed.
    # Sized for a two-site operator; raise them deliberately before scaling.
    # -----------------------------------------------------------------
    ANTHROPIC_API_KEY: str = ""
    # 🔴 WHICH TENANTS MAY SPEND. The key is server-wide; this is not.
    #
    # Without this, setting a key switches the AI features on for EVERY tenant
    # on the box at once, because the endpoints are gated by role and nothing
    # else. Four production tenants share this server, so the ceiling would be
    # the per-tenant cap multiplied by four, which is not what "enable it for
    # this client" means to anybody who asks for it.
    #
    # Comma-separated tenant slugs. EMPTY MEANS NO TENANT, deliberately: this is
    # a second, independent opt-in lock alongside the key, and the safe failure
    # is the loud one. A forgotten setting here shows up instantly as "AI is not
    # enabled for this restaurant" during testing and costs nothing; the reverse
    # default would fail silently, by spending money.
    #
    # A `str` and not a `list[str]` on purpose -- see CLAUDE.md: pydantic-settings
    # v2 tries to JSON-decode a list-typed env var before any validator runs, so
    # a comma-separated value raises. Split it in the property below, the same
    # way CORS_ORIGINS does.
    AI_ENABLED_TENANT_SLUGS: str = ""
    # One constant, one place. Overridable so the operator can choose a cheaper
    # tier for their own volume; that is their decision, not a default.
    AI_MODEL: str = "claude-opus-5"
    # A delivery note is a page of text. This bounds the output, not the input.
    AI_MAX_OUTPUT_TOKENS: int = 4000
    # Uploaded documents. 8MB comfortably covers a phone photo of an A4 note
    # and stays well inside the API's 32MB request limit.
    AI_MAX_UPLOAD_BYTES: int = 8 * 1024 * 1024
    AI_DAILY_CALL_CAP_PER_TENANT: int = 200
    AI_DAILY_TOKEN_CAP_PER_TENANT: int = 2_000_000
    # 🔴 THE CAP THAT ACTUALLY BOUNDS THE INVOICE, and the one to change.
    #
    # The two caps above are denominated in the wrong unit for the question
    # anybody actually asks, which is "what is the worst this can cost me?".
    # Worked out on `claude-opus-5` with AI_MAX_OUTPUT_TOKENS=4000, the two of
    # them together still permit ~$27.50 a day, about $825 a month:
    #   200 calls x 4000 output tokens = 800k out  @ $25/Mtok = $20.00
    #   remaining 1.2M of the token cap as input   @ $6.25/Mtok = $7.50
    # That is a surprise invoice, which is precisely what a cap is for.
    #
    # So spend is capped in money, per tenant per UTC day, summed from the
    # `estimated_cost_usd` column that every call already writes. Checked
    # BEFORE the call, like the others, and degrading the same graceful way.
    #
    # ⚠️ It is a CEILING, not a budget, and it can be overshot by at most one
    # call: a tenant sitting at $4.99 is still under the cap and is allowed one
    # more request. Worst realistic overshoot is a few cents.
    #
    # ⚠️ The sum is an ESTIMATE from `_RATES_PER_MTOK` in ai_client.py, not an
    # invoice. If Anthropic changes its prices and that table is not updated,
    # this cap drifts with it. The Anthropic console is the authority; reconcile
    # against it. This is why the call and token caps are kept as well: they are
    # denominated in units that cannot silently drift.
    #
    # For scale: a delivery-note scan measured $0.026 on 2026-08-26, so $5.00
    # is roughly 190 scans a day, not a handful. Set it to what the operator
    # should be allowed to spend, not to what you expect them to use.
    AI_DAILY_COST_CAP_USD_PER_TENANT: Decimal = Decimal("5.00")

    @property
    def ai_enabled_tenant_slugs(self) -> set[str]:
        """Slugs allowed to spend. Lower-cased so a capitalised env var still works."""
        return {
            part.strip().lower()
            for part in self.AI_ENABLED_TENANT_SLUGS.split(",")
            if part.strip()
        }

    @property
    def ai_configured(self) -> bool:
        """AI is opt-in. Without a key, nothing calls a model.

        Deliberately not fatal, for the same reason `email_configured` is not:
        receiving goods and ordering stock are the product; the model is an
        assist on top of them.
        """
        return bool(self.ANTHROPIC_API_KEY)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()

# Guard: refuse to start in production with insecure SECRET_KEY
if settings.is_production and settings.SECRET_KEY in _INSECURE_DEFAULTS:
    print(
        "FATAL: SECRET_KEY is set to an insecure default. "
        "Set a strong, unique SECRET_KEY environment variable for production.",
        file=sys.stderr,
    )
    sys.exit(1)
