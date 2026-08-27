"""The OCR `notes` field is shown to a client word for word.

Two things actually reached a customer's screen from it during UAT:

  F41  `invoice "u2014 it is a slide` -- a literal \\u2014 escape, not an em dash.
  F42  `... does not match any order line and is returned as -1.` -- the
       internal no-match sentinel, quoted at the client.

The prompt now forbids both, but a prompt is a request rather than a guarantee,
so `_clean_prose` removes them on the way out. These tests pin that, and pin
just as hard that ordinary prose is left alone -- a sanitiser that quietly
mangles good text is worse than the bug it fixes.
"""

import pytest

from app.services.ai_procurement import _clean_prose


class TestEscapesNeverReachTheClient:
    def test_a_literal_unicode_escape_becomes_readable_text(self):
        out = _clean_prose(
            "The supplied image is not a delivery note \\u2014 it is a slide."
        )
        assert "u2014" not in out
        assert "\\u" not in out
        assert out == "The supplied image is not a delivery note - it is a slide."

    def test_curly_quotes_arriving_as_escapes_become_plain_quotes(self):
        out = _clean_prose('Titled \\u201cTest assets only\\u201d.')
        assert out == 'Titled "Test assets only".'

    def test_a_real_em_dash_glyph_is_also_normalised(self):
        # Not an escape this time, the actual character.
        out = _clean_prose("Two rows were smudged — check them.")
        assert "—" not in out
        assert out == "Two rows were smudged - check them."

    def test_control_characters_are_stripped(self):
        assert _clean_prose("Flour\x08 row is fine.") == "Flour row is fine."


class TestTheInternalSentinelIsNotQuotedAtTheClient:
    def test_the_minus_one_sentinel_is_removed(self):
        out = _clean_prose(
            "The 'Sugar' row (10 kg @ 2.40) does not match any order line "
            "and is returned as -1."
        )
        assert "-1" not in out
        assert "returned as" not in out
        assert out.startswith("The 'Sugar' row (10 kg @ 2.40) does not match")

    def test_the_sentence_keeps_its_full_stop(self):
        """Cutting the sentinel off the end takes the full stop with it."""
        out = _clean_prose("The Sugar row does not match any order line and is returned as -1.")
        assert out.endswith("."), f"reads as truncated: {out!r}"


class TestOrdinaryProseSurvivesUntouched:
    @pytest.mark.parametrize(
        "text",
        [
            "Two rows were smudged; check them before booking in.",
            "The quantity for Butter was handwritten and is low confidence.",
            "Everything on the note matched the order.",
            # A legitimate negative number must NOT be eaten by the sentinel rule.
            "The adjustment was -1 kg, recorded as waste.",
        ],
    )
    def test_untouched(self, text):
        assert _clean_prose(text) == text

    def test_empty_and_missing_become_none(self):
        assert _clean_prose(None) is None
        assert _clean_prose("") is None
        assert _clean_prose("   ") is None
