"""The glossary: one Markdown file, read by the docs and the page."""

import pytest

from hindcast import app, glossary

ROOT = glossary.GLOSSARY.parent.parent


def test_the_glossary_parses_into_categories_with_terms():
    categories = glossary.load(ROOT)
    assert [c.title for c in categories] == [
        "Cases and data",
        "Investigation",
        "Safety",
        "Retrieval",
        "Evaluation",
        "Platform and operations",
    ]
    assert all(len(c.terms) >= 10 for c in categories)
    assert all(t.term and t.meaning for c in categories for t in c.terms)


def test_every_term_the_page_uses_is_in_the_glossary():
    categories = glossary.load(ROOT)
    missing = [t for t in app.PAGE_TERMS if glossary.lookup(categories, t) is None]
    assert missing == []


def test_glossary_links_resolve_to_files():
    import re

    text = (ROOT / glossary.GLOSSARY).read_text(encoding="utf-8")
    links = [x for x in re.findall(r"\]\(([^)#]+)", text) if not x.startswith("http")]
    assert links, "the glossary links its sources"
    assert [x for x in links if not (ROOT / "docs" / x).exists()] == []


def test_lookup_turns_relative_links_into_repository_links():
    row = "| **X** | See [d](decisions/0001-scope.md) and [r](../README.md). |"
    categories = glossary.parse(f"## A\n\n| Term | Meaning |\n| --- | --- |\n{row}\n")
    meaning = glossary.lookup(categories, "x")
    assert meaning == (
        f"See [d]({glossary.REPOSITORY}docs/decisions/0001-scope.md)"
        f" and [r]({glossary.REPOSITORY}README.md)."
    )
    assert glossary.lookup(categories, "nope") is None


def test_a_category_without_terms_is_an_error():
    with pytest.raises(ValueError, match="no terms"):
        glossary.parse("## Empty\n\n## B\n\n| Term | Meaning |\n| --- | --- |\n| a | b |\n")


def test_a_term_listed_twice_is_an_error():
    head = "| Term | Meaning |\n| --- | --- |\n"
    text = f"## A\n\n{head}| **Case** | one |\n\n## B\n\n{head}| case | two |\n"
    with pytest.raises(ValueError, match="twice"):
        glossary.parse(text)


def test_an_escaped_pipe_stays_in_the_meaning():
    categories = glossary.parse("## A\n\n| Term | Meaning |\n| --- | --- |\n| x | a \\| b |\n")
    assert categories[0].terms[0].meaning == "a | b"
