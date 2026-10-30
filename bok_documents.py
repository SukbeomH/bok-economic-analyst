"""Read PDF pages and search their text without models, indexes, or network calls."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pymupdf


@dataclass(frozen=True)
class PdfPage:
    """A PDF page with a filename and a one-based page number."""

    source: str
    page: int
    text: str


@dataclass(frozen=True)
class SearchResult:
    """Text search results, including empty corpus and no-match outcomes."""

    status: Literal["ok", "empty_corpus", "no_matches"]
    query: str
    results: tuple[PdfPage, ...]
    method: Literal["text"] = "text"


def load_pdf_pages(data_dir: Path) -> tuple[PdfPage, ...]:
    """Read all PDF pages in a directory, failing if any PDF cannot be read."""
    if not data_dir.is_dir():
        raise ValueError(f"PDF directory does not exist: {data_dir}")
    pages = []
    for path in sorted(data_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() != ".pdf":
            continue
        try:
            with pymupdf.open(path) as document:
                if document.needs_pass:
                    raise ValueError("password-protected PDF")
                pages.extend(PdfPage(path.name, page.number + 1, page.get_text()) for page in document)
        except (OSError, RuntimeError, ValueError) as error:
            raise ValueError(f"Cannot read PDF {path.name}: {error}") from error
    return tuple(pages)


def search_documents(query: str, data_dir: Path, limit: int = 5) -> SearchResult:
    """Rank pages by distinct matching whitespace-separated terms, then filename and page."""
    terms = set(query.casefold().split())
    if not terms:
        raise ValueError("Query must contain text")
    if limit < 1:
        raise ValueError("Limit must be positive")
    pages = load_pdf_pages(data_dir)
    if not pages:
        return SearchResult("empty_corpus", query, ())
    ranked = []
    for page in pages:
        text = " ".join(page.text.casefold().split())
        matches = sum(term in text for term in terms)
        if matches:
            ranked.append((matches, page))
    ranked.sort(key=lambda item: (-item[0], item[1].source, item[1].page))
    results = tuple(page for _, page in ranked[:limit])
    return SearchResult("ok" if results else "no_matches", query, results)
