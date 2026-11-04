from hindcast.excerpts import Excerpt, library_items, resolve
from hindcast.result import Citation
from test_investigate import EVIDENCE

EXTRACT = {
    "doc_id": "a",
    "published_at": "2025-01-01",
    "sections": [{"section_id": "lib/a/s1", "heading": "What happened", "markdown": "Body."}],
    "figures": [
        {
            "figure_id": "lib/a/fig1",
            "source_url": "https://example.com/fig1.png",
            "sha256": "0" * 64,
            "description": "A line drops.",
            "alt_text": "Requests per second",
            "text_in_image": "rps",
            "display": True,
        }
    ],
    "dropped": [],
}
LIBRARY = library_items([EXTRACT], {"a": "An earlier outage"})


def test_resolve_update() -> None:
    excerpt = resolve(Citation("case", "dev/u1"), EVIDENCE, LIBRARY)
    assert excerpt == Excerpt(
        "case", "dev/u1", "2026-02-20T18:45:17Z investigating", "Looking into it."
    )


def test_resolve_the_resolved_update_shows_its_text_was_withheld() -> None:
    excerpt = resolve(Citation("case", "dev/u2"), EVIDENCE, LIBRARY)
    assert excerpt is not None
    assert excerpt.title == "2026-02-20T19:10:00Z resolved"
    assert excerpt.text == "(text withheld)"


def test_resolve_chart_gives_what_the_model_was_shown() -> None:
    excerpt = resolve(Citation("case", "dev/chart1"), EVIDENCE, LIBRARY)
    assert excerpt == Excerpt(
        "case", "dev/chart1", "Chart: Traffic chart", "Description (model output): Traffic dips."
    )


def test_resolve_library_section() -> None:
    excerpt = resolve(Citation("library", "lib/a/s1"), EVIDENCE, LIBRARY)
    assert excerpt == Excerpt("library", "lib/a/s1", "An earlier outage: What happened", "Body.")


def test_resolve_library_figure_joins_its_fields_as_the_index_does() -> None:
    excerpt = resolve(Citation("library", "lib/a/fig1"), EVIDENCE, LIBRARY)
    assert excerpt is not None
    assert excerpt.title == "An earlier outage: figure"
    assert excerpt.text == "A line drops.\n\nRequests per second\n\nrps"


def test_resolve_unknown_is_none() -> None:
    assert resolve(Citation("case", "dev/u9"), EVIDENCE, LIBRARY) is None
    assert resolve(Citation("library", "lib/a/s9"), EVIDENCE, LIBRARY) is None
    # A case ref under the library source, or the reverse, does not resolve.
    assert resolve(Citation("library", "dev/u1"), EVIDENCE, LIBRARY) is None
    assert resolve(Citation("case", "lib/a/s1"), EVIDENCE, LIBRARY) is None
    assert resolve(Citation("", "dev/u1"), EVIDENCE, LIBRARY) is None
