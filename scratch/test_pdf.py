def create_text_pdf(text: str, title: str = "Cover Letter") -> bytes:
    # Minimal valid PDF-1.4 file with text wrapping and standard Helvetica font
    lines = []
    for paragraph in text.splitlines():
        if not paragraph.strip():
            lines.append("")
            continue
        words = paragraph.split()
        curr = ""
        for w in words:
            if len(curr) + len(w) + 1 <= 85:
                curr = f"{curr} {w}" if curr else w
            else:
                lines.append(curr)
                curr = w
        if curr:
            lines.append(curr)
    
    # PDF page is 612 x 792 (Letter). Margins: 50pt.
    # Text flow: y starts at 720, decrements by 14
    content_lines = ["BT", "/F1 11 Tf", "50 720 Td", "14 TL"]
    for i, line in enumerate(lines[:45]):  # Up to 45 lines per page
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if i == 0:
            content_lines.append(f"({escaped}) Tj")
        else:
            content_lines.append(f"T* ({escaped}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")
    
    objects = []
    # 1 0 obj: Catalog
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    # 2 0 obj: Pages
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    # 3 0 obj: Page
    objects.append(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n")
    # 4 0 obj: Contents stream
    objects.append(f"4 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream\nendobj\n")
    # 5 0 obj: Font
    objects.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    body = b"".join(objects)
    
    # Cross-reference table
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

pdf_bytes = create_text_pdf("Dear Hiring Manager,\n\nI am writing to apply for the Software Engineering Intern position.\n\nSincerely,\nCandidate")
print("Generated PDF size:", len(pdf_bytes))
import pdfplumber, io
with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
    print("Extracted from generated PDF:", repr(pdf.pages[0].extract_text()[:100]))
