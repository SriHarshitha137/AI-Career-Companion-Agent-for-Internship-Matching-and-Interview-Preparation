"""Pure Python PDF generator for clean, self-contained cover-letter downloads."""

from __future__ import annotations


def generate_cover_letter_pdf(content: str, title: str = "Cover Letter") -> bytes:
    """Generate a clean, standard PDF-1.4 document containing only cover-letter text."""
    lines: list[str] = []
    for paragraph in content.splitlines():
        trimmed = paragraph.strip()
        if not trimmed:
            lines.append("")
            continue
        words = trimmed.split()
        curr = ""
        for w in words:
            if len(curr) + len(w) + 1 <= 82:
                curr = f"{curr} {w}" if curr else w
            else:
                lines.append(curr)
                curr = w
        if curr:
            lines.append(curr)

    # Standard Letter page: 612 x 792. Margins: 54pt (0.75 in).
    content_lines = ["BT", "/F1 11 Tf", "54 720 Td", "15 TL"]
    for i, line in enumerate(lines[:50]):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if i == 0:
            content_lines.append(f"({escaped}) Tj")
        else:
            content_lines.append(f"T* ({escaped}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects: list[bytes] = []
    # 1 0 obj: Catalog
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    # 2 0 obj: Pages
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    # 3 0 obj: Page
    objects.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    )
    # 4 0 obj: Contents stream
    objects.append(f"4 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream\nendobj\n")
    # 5 0 obj: Standard Font
    objects.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    body = b"".join(objects)

    xref_offset = len(header) + len(body)
    offsets = [0]
    curr_off = len(header)
    for obj in objects:
        offsets.append(curr_off)
        curr_off += len(obj)

    xref = f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii")
    for off in offsets[1:]:
        xref += f"{off:010d} 00000 n \n".encode("ascii")
    trailer = f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")

    return header + body + xref + trailer
