"""MoU report files (Screen 19/20).

WeasyPrint is the production renderer (Tamil glyphs need Noto Sans Tamil).
Until it is installed, `render_pdf` builds a small, valid PDF with the
report title, generated date and data-as-of date so downloads work end to end.
"""
import datetime

from services.storage import get_storage


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def render_pdf(title: str, lines: list) -> bytes:
    """A one-page PDF (Helvetica, ASCII)."""
    content_lines = ["BT", "/F1 18 Tf", "50 760 Td", f"({_pdf_escape(title)}) Tj", "/F1 11 Tf"]
    y = 730
    for line in lines:
        y -= 18
        content_lines.append(f"1 0 0 1 50 {y} Tm ({_pdf_escape(line)}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def ensure_report_file(report_id: str, title: str, generated_at: datetime.datetime, data_as_of: datetime.date,
                       summary_lines: list) -> tuple:
    """Create the PDF for a report run in storage if missing. Returns (storage_key, size_kb)."""
    key = f"reports/{report_id}.pdf"
    storage = get_storage()
    if not storage.exists(key):
        lines = [
            f"Generated: {generated_at.strftime('%d %b %Y %H:%M')}",
            f"Data as of: {data_as_of.strftime('%d %b %Y')}",
            "Industry-Ready Engineer Program - Demo Engineering College",
            "",
        ] + summary_lines
        storage.put(key, render_pdf(title, lines), "application/pdf")
    return key, max(1, storage.size(key) // 1024)
