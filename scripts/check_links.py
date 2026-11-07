"""Check every relative Markdown link and heading anchor in the repository.

Usage: python scripts/check_links.py [ROOT]

Walks ROOT for ``*.md`` files, skipping dot-directories, ``build``, and
``node_modules``. A link is bad when its target file is missing or its
``#fragment`` names no heading in the target page. Fragments follow GitHub's
slug rule: lowercase, punctuation dropped, spaces to hyphens, and ``-1``,
``-2`` for repeated headings. Prints each bad link and ends with
``N links, M bad``; the exit code is 1 when M is not 0.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

SKIP_DIRS = {"build", "node_modules"}
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$", re.M)
FENCE = re.compile(r"```.*?```", re.S)


def slug(text: str) -> str:
    """GitHub's heading slug: strip code spans, links, and emphasis, then punctuation."""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_]", "", text).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(page: Path) -> set[str]:
    """Every anchor GitHub renders for the page's headings, fenced code excluded."""
    seen: Counter[str] = Counter()
    out: set[str] = set()
    for match in HEADING.finditer(FENCE.sub("", page.read_text(encoding="utf-8"))):
        base = slug(match.group(1))
        n = seen[base]
        seen[base] += 1
        out.add(base if n == 0 else f"{base}-{n}")
    return out


def markdown_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*.md")):
        parts = path.relative_to(root).parts[:-1]
        if any(p.startswith(".") or p in SKIP_DIRS for p in parts):
            continue
        files.append(path)
    return files


def check(root: Path) -> tuple[int, list[str]]:
    """Return the link count and one line per bad link."""
    root = root.resolve()
    cache: dict[Path, set[str]] = {}
    total = 0
    bad: list[str] = []
    for page in markdown_files(root):
        text = FENCE.sub("", page.read_text(encoding="utf-8"))
        for match in LINK.finditer(text):
            target = match.group(1)
            if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("//"):
                continue  # a URL, not a path
            total += 1
            path, _, fragment = target.partition("#")
            dest = page if path == "" else (page.parent / path).resolve()
            rel = page.relative_to(root)
            if path and not dest.exists():
                bad.append(f"{rel}: missing {target}")
                continue
            if fragment and dest.is_file() and dest.suffix == ".md":
                if dest not in cache:
                    cache[dest] = anchors(dest)
                if fragment.lower() not in cache[dest]:
                    bad.append(f"{rel}: no anchor {target}")
    return total, bad


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    total, bad = check(root)
    for line in bad:
        print(line)
    print(f"{total} links, {len(bad)} bad")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
