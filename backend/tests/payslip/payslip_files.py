"""Synthetic payslip files for the tests: built in memory, never a real person's.

Every file carries an invented name, ID-like number and bank account, so a test can assert none
of them is ever extracted, stored or logged.
"""

import io
import struct
import zlib

FAKE_NAME = "Dana Bdaya"  # invented
FAKE_ID = "000000018"  # invented, ID-shaped
FAKE_BANK = "12-345-678901"  # invented
SECRETS = (FAKE_NAME, FAKE_ID, FAKE_BANK)


def pdf(pages: int = 1, padding: int = 0, text: str = "") -> bytes:
    """A valid PDF with `pages` pages (Helvetica text), the fake identifiers on page 1, and an
    optional unreferenced stream of `padding` bytes (to make it big)."""
    line = f"Strauss payslip {FAKE_NAME} ID {FAKE_ID} bank {FAKE_BANK} {text}".encode("latin-1")
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(pages))
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [" + kids.encode() + b"] /Count %d >>" % pages,
    ]
    font = 3 + 2 * pages
    for i in range(pages):
        content = b"BT /F1 12 Tf 72 720 Td (" + (line if i == 0 else b"page") + b") Tj ET"
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>" % (font, 4 + 2 * i)
        )
        objects.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    if padding:
        objects.append(b"<< /Length %d >>\nstream\n" % padding + b"A" * padding + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


def encrypted_pdf() -> bytes:
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf())))
    writer.encrypt("secret", algorithm="RC4-128")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def png(size: int = 8) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + kind + data + crc

    header = struct.pack(">IIBBBBB", size, size, 8, 0, 0, 0, 0)
    rows = b"".join(b"\x00" + b"\xff" * size for _ in range(size))
    # a tEXt chunk with the fake identifiers, as a scanner's metadata might carry
    text = b"Comment\x00" + f"{FAKE_NAME} {FAKE_ID}".encode()
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"tEXt", text)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def jpeg() -> bytes:
    """JPEG-shaped bytes (SOI, a comment with the fake identifiers, EOI): enough for the
    magic-byte check and the scripted extractor; never sent to a real model."""
    comment = f"{FAKE_NAME} {FAKE_ID}".encode()
    return b"\xff\xd8\xff\xfe" + struct.pack(">H", len(comment) + 2) + comment + b"\xff\xd9"
