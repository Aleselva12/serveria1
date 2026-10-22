"""Commercial Word: conservative customer index and in-memory append preview.

Never changes a source file. Publication needs separate user approval.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import re
import unicodedata
from docx import Document
from lxml import etree

DIVIDER = re.compile(r"^\\s*[-—–_]{5,}\\s*$")
DATE = re.compile(r"^\\s*(?:\\d{1,2}/\\d{1,2}/\\d{2,4}|GIRO DI [A-ZÀ-Ú ]+(?:\\d{2,4})?)\\s*$", re.I)


@dataclass(frozen=True)
class CustomerBlock:
    heading: str
    start: int
    stop: int
    identity_lines: tuple[str, ...]
    document_sha256: str


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).casefold()
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def heading(text: str) -> bool:
    value = text.strip()
    if not value or DATE.fullmatch(value) or DIVIDER.fullmatch(value):
        return False
    prefixes = ("LIDO", "HOTEL", "VILLAGGIO", "RAGNO", "SOUTH BEACH", "WHITE BEACH", "MAGO", "LA PERLA", "IL TRAMONTO", "IL CORALLO")
    return value.upper().startswith(prefixes) or (value.isupper() and len(value) < 100 and not any(c.isdigit() for c in value))


def parse(content: bytes) -> list[CustomerBlock]:
    document = Document(BytesIO(content))
    lines = [p.text.strip() for p in document.paragraphs]
    checksum = sha256(content).hexdigest()
    result: list[CustomerBlock] = []
    start = 0
    for stop in range(len(lines) + 1):
        if stop < len(lines) and not DIVIDER.fullmatch(lines[stop]):
            continue
        paragraphs = [(i, lines[i]) for i in range(start, stop) if lines[i]]
        if paragraphs:
            position, title = paragraphs[0]
            if not heading(title) and len(paragraphs) > 1 and heading(paragraphs[1][1]):
                position, title = paragraphs[1]
            if heading(title):
                contacts = tuple(value for i, value in paragraphs if position < i <= position + 4 and not DATE.fullmatch(value))
                result.append(CustomerBlock(title, position, stop, contacts, checksum))
        start = stop + 1
    return result


def search(content: bytes, query: str, limit: int = 8) -> list[CustomerBlock]:
    if not query.strip() or len(query) > 200:
        raise ValueError("Ricerca cliente non valida.")
    term = normalize(query)
    return [b for b in parse(content) if term in normalize(b.heading + " " + " ".join(b.identity_lines))][:limit]
