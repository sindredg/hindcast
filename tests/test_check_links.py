"""The link checker finds a missing file and a missing anchor, and passes a clean tree."""

from pathlib import Path

import check_links


def write(root: Path, name: str, text: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_clean_tree_has_no_bad_links(tmp_path: Path) -> None:
    write(tmp_path, "README.md", "# Top\n\n[docs](docs/page.md#a-section) [self](#top)\n")
    write(tmp_path, "docs/page.md", "# Page\n\n## A section\n\n[up](../README.md)\n")
    total, bad = check_links.check(tmp_path)
    assert (total, bad) == (3, [])


def test_missing_file_and_anchor_are_reported(tmp_path: Path) -> None:
    write(tmp_path, "README.md", "# Top\n\n[gone](nowhere.md) [frag](docs/page.md#not-there)\n")
    write(tmp_path, "docs/page.md", "# Page\n")
    total, bad = check_links.check(tmp_path)
    assert total == 2
    assert bad == ["README.md: missing nowhere.md", "README.md: no anchor docs/page.md#not-there"]


def test_slugs_follow_github(tmp_path: Path) -> None:
    page = (
        "# T\n\n## Step `one`: a.b (2026-11-07)\n\n## Dup\n\n## Dup\n\n```\n## not a heading\n```\n"
    )
    write(tmp_path, "p.md", page)
    assert check_links.anchors(tmp_path / "p.md") == {"t", "step-one-ab-2026-11-07", "dup", "dup-1"}


def test_urls_and_fenced_code_are_skipped(tmp_path: Path) -> None:
    write(tmp_path, "p.md", "# P\n\n[x](https://example.com/a#b)\n\n```\n[y](missing.md)\n```\n")
    assert check_links.check(tmp_path) == (0, [])
