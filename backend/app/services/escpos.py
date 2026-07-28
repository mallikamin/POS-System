"""ESC/POS byte generation for thermal receipt printers.

This is the first real printing implementation in the product. Before this,
"thermal printer support" meant `window.print()` against an 80 mm CSS layout
(`frontend/src/components/pos/ReceiptModal.tsx`), which is a browser print
dialog, not a printer protocol.

Why hand-rolled instead of `python-escpos`
------------------------------------------
That library pulls in Pillow and USB backends to drive printers directly over
USB/serial. We do neither: we emit bytes and hand them to something else (the
RawBT app on the shop tablet, or a socket) to deliver. A kitchen ticket needs
about eight commands. Hand-rolling keeps the dependency list on a 2 GB server
unchanged and, more usefully, means the exact bytes are visible and unit
testable when we are debugging against a printer model we have never seen, in
a shop 6000 km away.

Encoding
--------
Text is encoded **CP437**, the default codepage of virtually every ESC/POS
printer. This is not a detail we can skip: the client is in the UK and every
ticket carries a pound sign. UTF-8 '£' is two bytes (0xC2 0xA3) and prints as
two pieces of line-noise. In CP437 it is a single byte, 0x9C.

References: Epson ESC/POS command reference (ESC @, ESC a, ESC E, GS !, GS V).
"""

from __future__ import annotations

# --- Commands -------------------------------------------------------------

ESC = b"\x1b"
GS = b"\x1d"

INIT = ESC + b"@"  # ESC @  -- reset to power-on defaults
ALIGN_LEFT = ESC + b"a\x00"
ALIGN_CENTER = ESC + b"a\x01"
ALIGN_RIGHT = ESC + b"a\x02"
BOLD_ON = ESC + b"E\x01"
BOLD_OFF = ESC + b"E\x00"
UNDERLINE_ON = ESC + b"-\x01"
UNDERLINE_OFF = ESC + b"-\x00"

# GS ! n -- n = ((width-1) << 4) | (height-1), each 1..8
SIZE_NORMAL = GS + b"!\x00"
SIZE_DOUBLE_HEIGHT = GS + b"!\x01"
SIZE_DOUBLE = GS + b"!\x11"  # double width AND height

# GS V 66 n -- partial cut after feeding n dots. Function B is the widely
# supported form; a bare `GS V 0` full cut is refused by some models that only
# implement partial cutting.
CUT = GS + b"V\x42\x00"

# ESC d n -- feed n lines
def feed(lines: int = 1) -> bytes:
    return ESC + b"d" + bytes([max(0, min(255, lines))])


# --- Text -----------------------------------------------------------------

# Characters CP437 cannot represent, mapped to something a kitchen can read
# rather than letting them become '?'. Curly quotes and dashes turn up
# constantly in menu text pasted from Word or a website.
_TRANSLITERATE = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "…": "...",
        " ": " ",
        "€": "EUR",
        "•": "*",
    }
)


def encode(text: str) -> bytes:
    """Encode text for the printer, never raising on odd input.

    A ticket that prints with one mangled character is recoverable. A ticket
    that raises and prints nothing loses the order.
    """
    return text.translate(_TRANSLITERATE).encode("cp437", errors="replace")


def wrap(text: str, width: int, indent: str = "") -> list[str]:
    """Wrap to the printer's column count, breaking over-long words.

    `textwrap` is deliberately not used: it collapses whitespace and, by
    default, refuses to break a long unbroken token, which silently produces a
    line wider than the paper.
    """
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = indent
        for word in paragraph.split():
            while len(word) > width - len(indent):
                # A token longer than the paper. Hard-break it.
                space = width - len(current)
                if space <= 0:
                    lines.append(current.rstrip())
                    current = indent
                    continue
                current += word[:space]
                word = word[space:]
                lines.append(current)
                current = indent
            if current.strip() and len(current) + 1 + len(word) > width:
                lines.append(current.rstrip())
                current = indent + word
            elif not current.strip():
                current = indent + word
            else:
                current += " " + word
        lines.append(current.rstrip())
    return lines


class Ticket:
    """Accumulates ESC/POS bytes for one ticket.

    `width` is the printer's characters-per-line in Font A: 48 for 80 mm paper,
    32 for 58 mm. Wrong value means wrapped or truncated lines, so it is
    configurable rather than assumed.
    """

    def __init__(self, width: int = 48) -> None:
        self.width = width
        self._buf = bytearray(INIT)

    # -- primitives --
    def raw(self, data: bytes) -> "Ticket":
        self._buf += data
        return self

    def text(self, value: str = "") -> "Ticket":
        """One or more lines of left-aligned text, wrapped to the paper.

        Leading whitespace is preserved and carried onto continuation lines.
        Without this, `text("    - Hot")` prints hard against the left margin
        and a modifier stops looking like it belongs to the item above it.
        """
        for paragraph in value.split("\n"):
            indent = paragraph[: len(paragraph) - len(paragraph.lstrip(" "))]
            for line in wrap(paragraph.strip(), self.width, indent=indent):
                self._buf += encode(line) + b"\n"
        return self

    def field(self, label: str, value: str, pad: int = 7) -> "Ticket":
        """A padded `label   value` line with a hanging indent when it wraps.

        Built line by line rather than via `text()`, because `wrap` collapses
        runs of spaces and would eat the padding that makes the labels form a
        column. A wrapped value lines up under itself, not under the label.
        """
        lines = wrap(value.strip(), self.width - pad) or [""]
        self._buf += encode(label.ljust(pad) + lines[0]) + b"\n"
        for line in lines[1:]:
            self._buf += encode(" " * pad + line) + b"\n"
        return self

    def center(self, value: str, *, bold: bool = False, big: bool = False) -> "Ticket":
        self._buf += ALIGN_CENTER
        if big:
            self._buf += SIZE_DOUBLE
        if bold:
            self._buf += BOLD_ON
        # Halve the usable width when characters are double width.
        for line in wrap(value, self.width // 2 if big else self.width):
            self._buf += encode(line) + b"\n"
        if bold:
            self._buf += BOLD_OFF
        if big:
            self._buf += SIZE_NORMAL
        self._buf += ALIGN_LEFT
        return self

    def bold(self, value: str) -> "Ticket":
        # Delegates to text() so bold lines keep their indentation too. An
        # emphasised item note has to stay indented under its item.
        self._buf += BOLD_ON
        self.text(value)
        self._buf += BOLD_OFF
        return self

    def rule(self, char: str = "-") -> "Ticket":
        self._buf += encode(char * self.width) + b"\n"
        return self

    def columns(self, left: str, right: str, *, bold: bool = False) -> "Ticket":
        """Left text, right-aligned value, padded to the full width.

        Used for money lines, where the amounts must form a column. If the two
        together exceed the paper, the left side is truncated -- the amount is
        the part that must never be lost.
        """
        space = self.width - len(right)
        if len(left) > space - 1:
            left = left[: max(0, space - 2)] + "."
        line = left.ljust(space) + right
        if bold:
            self._buf += BOLD_ON
        self._buf += encode(line) + b"\n"
        if bold:
            self._buf += BOLD_OFF
        return self

    def feed(self, lines: int = 1) -> "Ticket":
        self._buf += feed(lines)
        return self

    def cut(self) -> "Ticket":
        # Feed before cutting or the cutter slices through the last lines --
        # the blade sits some way above the print head.
        self._buf += feed(4) + CUT
        return self

    def bytes(self) -> bytes:
        return bytes(self._buf)

    def preview(self) -> str:
        return preview(self.bytes())


def preview(payload: bytes) -> str:
    """Render ESC/POS bytes as the text a printer would put on paper.

    Takes bytes rather than living only on `Ticket` so it works on a payload
    pulled from a log or an endpoint. That is the support case: "show me
    exactly what came out of the printer at 19:14" without owning the printer.

    Strips whole commands, argument bytes included. Stripping only the ESC and
    GS markers would leave the arguments behind as stray characters and make
    every line look wider than it is.
    """
    out = payload
    for token in (
        INIT, ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT, BOLD_ON, BOLD_OFF,
        UNDERLINE_ON, UNDERLINE_OFF, SIZE_NORMAL, SIZE_DOUBLE_HEIGHT,
        SIZE_DOUBLE, CUT,
    ):
        out = out.replace(token, b"")

    # Whatever is left: ESC d n (feed) is the only multi-byte command we emit.
    cleaned = bytearray()
    i = 0
    while i < len(out):
        if out[i : i + 2] == ESC + b"d" and i + 2 < len(out):
            cleaned += b"\n" * out[i + 2]
            i += 3
            continue
        cleaned.append(out[i])
        i += 1
    return bytes(cleaned).decode("cp437", errors="replace")
