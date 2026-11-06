"""The glossary: docs/glossary.md, read once for the docs and for the page.

The Markdown file is the only source. Each `## ` heading is a category and
each row of the table under it is a term and its meaning. The page shows the
same rows, with the relative links turned into links to the repository, and
uses a term's meaning as the help text next to the page's own labels.
"""

import posixpath
import re
from dataclasses import dataclass
from pathlib import Path

GLOSSARY = Path("docs/glossary.md")
# Where the page sends a relative link in the glossary: the file on GitHub.
REPOSITORY = "https://github.com/sindredg/hindcast/blob/main/"
_LINK = re.compile(r"\]\((?!https?://|#)([^)\s]+)\)")
_ROW = re.compile(r"^\|(.+)\|\s*$")


@dataclass(frozen=True)
class Term:
    term: str
    meaning: str  # Markdown, as written in the file


@dataclass(frozen=True)
class Category:
    title: str
    terms: tuple[Term, ...]


def _cells(line: str) -> list[str] | None:
    match = _ROW.match(line.strip())
    if match is None:
        return None
    # A pipe inside a cell is written as \| in the file.
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", match.group(1))]


def parse(text: str) -> list[Category]:
    """The categories in file order; a heading without a table is an error."""
    categories: list[Category] = []
    title: str | None = None
    rows: list[Term] = []

    def close() -> None:
        if title is None:
            return
        if not rows:
            raise ValueError(f"glossary category {title!r} has no terms")
        categories.append(Category(title, tuple(rows)))

    for line in text.splitlines():
        if line.startswith("## "):
            close()
            title, rows = line.removeprefix("## ").strip(), []
            continue
        cells = _cells(line) if title is not None else None
        if cells is None or len(cells) != 2:
            continue
        term, meaning = cells
        # The header row and the --- row under it.
        if term.lower() == "term" or set(term) <= set("-: "):
            continue
        rows.append(Term(term.strip("*").strip(), meaning))
    close()
    terms = [t.term.lower() for c in categories for t in c.terms]
    duplicates = sorted({t for t in terms if terms.count(t) > 1})
    if duplicates:
        raise ValueError(f"glossary terms appear twice: {', '.join(duplicates)}")
    return categories


def load(root: Path) -> list[Category]:
    return parse((root / GLOSSARY).read_text(encoding="utf-8"))


def absolute_links(meaning: str, page: Path = GLOSSARY) -> str:
    """Relative links resolved against the glossary's folder, as repository URLs."""

    def repl(match: re.Match[str]) -> str:
        target = posixpath.normpath(posixpath.join(page.parent.as_posix(), match.group(1)))
        return f"]({REPOSITORY}{target})"

    return _LINK.sub(repl, meaning)


def lookup(categories: list[Category], term: str) -> str | None:
    """A term's meaning with repository links, for a help tooltip; None when absent."""
    wanted = term.lower()
    for category in categories:
        for entry in category.terms:
            if entry.term.lower() == wanted:
                return absolute_links(entry.meaning)
    return None
