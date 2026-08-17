"""Repair obvious typos in a customer's email domain before we send to it (OI-86).

Two of our first 103 customers gave an address that cannot receive mail --
`gmail.con` and `gmail.cim`. They got no order confirmation, no review request
and no campaign, and nobody noticed for sixteen days.

Malik's rule, 2026-08-17, and it is the whole design:

    "i dont want to screwup on custom domains but gmail.com vs gmial gmali etc
     .com .co .con for gmail variants - this should be common sense. so only
     common sense. but in any case keep the customer original email recorded so
     anytime we have to resort to see what he actually wrote that should be
     preserved."

So:

* **Only the big consumer providers are in scope.** A custom or business domain
  is never touched. `spyco.co.uk` and `marvelous.com` are real customers of
  ours and look odd; they must survive untouched. The provider list IS the
  safety guard -- `gmail.co` is plainly wrong because Google runs no mail
  there, while `mybusiness.co` is perfectly fine, and the list is what tells
  those two apart.

* **The original is never overwritten.** This function returns a corrected copy
  and nothing here writes to the database. `orders.customer_email` keeps
  exactly what the customer typed, forever, so there is always a way to see
  what they actually wrote.

⚠️ **Curated tables, deliberately, NOT edit distance.** Levenshtein looks like
the obvious tool and it is a trap here: `email.com` is one character from
`gmail.com` and is a real domain owned by mail.com, so a distance-1 rule would
silently redirect a real customer's mail to Google. A curated table cannot
produce that class of error, is predictable, and is trivial to extend when a new
typo shows up in the data.

Applied at SEND time rather than at order creation, on purpose: it needs no
migration, it covers every send path (order emails, the review request, the
campaign sender), and it repairs addresses already in the database -- our two
dead ones included -- without a backfill.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Canonical domains for the providers we will correct TO. Taken from our own
#: customer table: these 14 cover 101 of 103 addresses on file.
PROVIDER_DOMAINS: frozenset[str] = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "hotmail.com",
        "hotmail.co.uk",
        "outlook.com",
        "live.co.uk",
        "icloud.com",
        "btinternet.com",
        "yahoo.co.uk",
        "yahoo.com",
        "aol.com",
        "aol.co.uk",
        "msn.com",
        "sky.com",
    }
)

#: Misspellings of a provider's NAME -> the correct name. Only these are ever
#: corrected. Add to this table when a new one turns up in the data; do not
#: replace it with a distance function (see the module docstring).
BRAND_TYPOS: dict[str, str] = {
    # gmail: 46 of our 103 customers, so by far the most typo-prone
    "gmial": "gmail",
    "gmali": "gmail",
    "gmai": "gmail",
    "gnail": "gmail",
    "gmaill": "gmail",
    "gmil": "gmail",
    "gmaul": "gmail",
    "gamil": "gmail",
    "ggmail": "gmail",
    # hotmail
    "hotmial": "hotmail",
    "hotmal": "hotmail",
    "hotmai": "hotmail",
    "hotmaill": "hotmail",
    "hotamil": "hotmail",
    "hotmali": "hotmail",
    # yahoo
    "yaho": "yahoo",
    "yahooo": "yahoo",
    "yhaoo": "yahoo",
    "yahoi": "yahoo",
    # outlook / live / icloud
    "outlok": "outlook",
    "outllok": "outlook",
    "oultook": "outlook",
    "iclould": "icloud",
    "icloud1": "icloud",
    "iclod": "icloud",
    # btinternet
    "btinternat": "btinternet",
    "btintenet": "btinternet",
    "btinernet": "btinternet",
}

#: Impossible or mistyped endings -> the correct ending. `co` is here ONLY
#: because it is applied exclusively to the providers above, where `gmail.co`
#: has no legitimate meaning. A custom domain ending in `.co` never reaches
#: this table.
TLD_TYPOS: dict[str, str] = {
    "con": "com",
    "cim": "com",
    "cpm": "com",
    "xom": "com",
    "vom": "com",
    "comm": "com",
    "ocm": "com",
    "cmo": "com",
    "cok": "com",
    "co": "com",
    "cm": "com",
    "couk": "co.uk",
    "co.ul": "co.uk",
    "co.ik": "co.uk",
    "cu.uk": "co.uk",
    "co.ukk": "co.uk",
}


def _split(address: str) -> tuple[str, str] | None:
    at = address.rfind("@")
    if at <= 0 or at == len(address) - 1:
        return None
    return address[:at], address[at + 1 :]


def normalise_email(address: str | None) -> tuple[str, bool]:
    """Return `(address_to_send_to, was_corrected)`.

    Never raises, never writes, and returns the input untouched whenever it is
    not confidently a typo of a known provider. The caller keeps the original.
    """
    raw = (address or "").strip()
    if not raw:
        return "", False

    parts = _split(raw)
    if parts is None:
        return raw, False
    local, domain = parts

    lowered = domain.lower()
    if lowered in PROVIDER_DOMAINS:
        return raw, False  # already right, nothing to do

    # Split "gmail.co.uk" into brand "gmail" and ending "co.uk"; "gmail.con"
    # into "gmail" and "con".
    bits = lowered.split(".")
    if len(bits) < 2:
        return raw, False
    brand = bits[0]
    ending = ".".join(bits[1:])

    fixed_brand = BRAND_TYPOS.get(brand, brand)
    fixed_ending = TLD_TYPOS.get(ending, ending)
    candidate = f"{fixed_brand}.{fixed_ending}"

    # ⚠️ THE GUARD. The repaired domain must land on a provider we listed. A
    # custom domain cannot reach one, so it is returned exactly as typed even
    # if its brand or ending happens to appear in a table above.
    if candidate == lowered or candidate not in PROVIDER_DOMAINS:
        return raw, False

    corrected = f"{local}@{candidate}"
    logger.info(
        "Email typo repaired for sending: %r -> %r (original is unchanged in the database)",
        raw,
        corrected,
    )
    return corrected, True
