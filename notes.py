"""Reading uploaded files and cutting notes into small chunks."""
import io
import re

from pypdf import PdfReader


def clean_text(text):
    text = text.replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(filename, data):
    """Return plain text from a .pdf, .txt or .md file (data = file bytes)."""
    name = filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    elif name.endswith((".txt", ".md")):
        text = data.decode("utf-8", errors="ignore")
    else:
        raise ValueError("Only PDF, TXT and MD files are supported.")
    return clean_text(text)


def chunk_text(text, chunk_words=150, overlap=30):
    """Split text into pieces of about `chunk_words` words; pieces overlap a little
    so a sentence cut at the edge still appears whole in one of them."""
    words = text.split()
    if not words:
        return []
    step = max(chunk_words - overlap, 1)
    chunks = []
    for start in range(0, len(words), step):
        chunks.append(" ".join(words[start:start + chunk_words]))
        if start + chunk_words >= len(words):
            break
    return chunks
