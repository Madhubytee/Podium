"""Pull text out of uploaded resumes, job posts, slides, and scripts."""

import io
from pathlib import Path

SUPPORTED = {".pdf", ".docx", ".pptx", ".txt", ".md"}


class UnsupportedFile(ValueError):
    pass


def extract_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if ext == ".docx":
        import docx

        doc = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if ext == ".pptx":
        from pptx import Presentation

        deck = Presentation(io.BytesIO(data))
        slides = []
        for i, slide in enumerate(deck.slides, 1):
            lines = [shape.text_frame.text for shape in slide.shapes if shape.has_text_frame and shape.text_frame.text.strip()]
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
                lines.append("Notes: " + slide.notes_slide.notes_text_frame.text)
            slides.append(f"Slide {i}: " + " / ".join(lines))
        return "\n".join(slides)
    if ext in {".txt", ".md"}:
        return data.decode("utf-8", errors="replace").strip()
    raise UnsupportedFile(f"Oli can read PDF, Word, PowerPoint, and text files, not {ext or 'this file'}.")


def guess_kind(filename: str, text: str) -> str:
    """resume / job_post / slides / script, used to label the file for Oli."""
    name = filename.lower()
    lowered = text[:3000].lower()
    if name.endswith(".pptx") or "slide" in name:
        return "slides"
    if "resume" in name or "cv" in name or ("experience" in lowered and "education" in lowered):
        return "resume"
    if "job" in name or "responsibilities" in lowered or "qualifications" in lowered:
        return "job_post"
    return "script"
