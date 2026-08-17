"""OI-86: repairing obvious email typos before sending, without touching custom domains.

The two halves are equally important and the second is the one that can do real
damage, so it is tested at least as hard as the first: a business customer whose
address merely LOOKS odd must come through completely untouched.
"""

import pytest

from app.services.email_normalise import normalise_email


# ---------------------------------------------------------------------------
# The two real dead addresses that started this
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "typed,expected",
    [
        ("chris@gmail.con", "chris@gmail.com"),
        ("chris@gmail.cim", "chris@gmail.com"),
    ],
)
def test_the_two_addresses_that_actually_failed_are_repaired(typed, expected):
    """Both are real, both are on our customer table, both have received nothing."""
    fixed, corrected = normalise_email(typed)
    assert fixed == expected
    assert corrected is True


# ---------------------------------------------------------------------------
# In scope: the big providers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "typed,expected",
    [
        # ending typos
        ("a@gmail.co", "a@gmail.com"),
        ("a@gmail.cpm", "a@gmail.com"),
        ("a@gmail.xom", "a@gmail.com"),
        ("a@hotmail.con", "a@hotmail.com"),
        ("a@outlook.con", "a@outlook.com"),
        ("a@yahoo.couk", "a@yahoo.co.uk"),
        ("a@hotmail.co.ukk", "a@hotmail.co.uk"),
        # brand typos
        ("a@gmial.com", "a@gmail.com"),
        ("a@gmali.com", "a@gmail.com"),
        ("a@gnail.com", "a@gmail.com"),
        ("a@gmai.com", "a@gmail.com"),
        ("a@hotmial.com", "a@hotmail.com"),
        ("a@iclould.com", "a@icloud.com"),
        # both at once
        ("a@gmial.con", "a@gmail.com"),
        ("a@hotmial.co", "a@hotmail.com"),
    ],
)
def test_common_sense_typos_on_known_providers_are_repaired(typed, expected):
    fixed, corrected = normalise_email(typed)
    assert fixed == expected
    assert corrected is True


# ---------------------------------------------------------------------------
# OUT of scope: everything else. This is the half that can cause harm.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "typed",
    [
        # Real customers of ours. They look odd and they are genuine.
        "a@spyco.co.uk",
        "a@marvelous.com",
        # A business on .co. Identical ending to gmail.co, and must NOT be
        # touched, because .co is Colombia and widely used. The provider list
        # is the only thing separating these two cases.
        "a@mybusiness.co",
        "a@somefirm.cm",
        # email.com is a REAL domain, one character from gmail.com. An
        # edit-distance rule would silently redirect this customer's mail to
        # Google. This test is the reason the module uses curated tables.
        "a@email.com",
        # Already correct, every provider.
        "a@gmail.com",
        "a@hotmail.co.uk",
        "a@btinternet.com",
        "a@sky.com",
        "a@aol.co.uk",
        # Plausible unknown domains.
        "a@proton.me",
        "a@fastmail.fm",
        "a@nhs.net",
        "a@council.gov.uk",
    ],
)
def test_anything_not_a_known_provider_is_left_exactly_as_typed(typed):
    fixed, corrected = normalise_email(typed)
    assert fixed == typed
    assert corrected is False


def test_a_brand_typo_on_an_unknown_ending_is_not_repaired():
    """`gmial` is a known typo, but `gmial.fr` cannot land on a provider we list,
    so it is left alone rather than guessed at."""
    fixed, corrected = normalise_email("a@gmial.fr")
    assert fixed == "a@gmial.fr"
    assert corrected is False


# ---------------------------------------------------------------------------
# Shape and safety
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["", "   ", None, "notanemail", "@gmail.con", "chris@"])
def test_junk_is_returned_untouched_and_never_raises(value):
    fixed, corrected = normalise_email(value)
    assert corrected is False
    assert fixed == (value or "").strip()


def test_the_local_part_is_never_altered():
    """Only the domain is ever touched. A misspelt name is not ours to guess."""
    fixed, _ = normalise_email("Chris.O'Brien+takeaway@gmail.con")
    assert fixed == "Chris.O'Brien+takeaway@gmail.com"


def test_an_at_sign_in_the_local_part_uses_the_last_one():
    fixed, corrected = normalise_email('"odd@name"@gmail.con')
    assert fixed == '"odd@name"@gmail.com'
    assert corrected is True


def test_repair_is_idempotent():
    once, _ = normalise_email("a@gmail.con")
    twice, corrected = normalise_email(once)
    assert twice == once
    assert corrected is False
