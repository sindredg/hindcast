import json

import pytest

from hindcast.cases import Case
from hindcast.library import LibraryDocument
from hindcast.library_extract import (
    Section,
    article,
    cut_later_text,
    display_allowed,
    extract_document,
    figure_sources,
    page_date,
)

URL = "https://blog.cloudflare.com/example-outage/"
# A hand-made page in the blog's shape: an image in the header and one in a
# related-post card sit outside the article body.
PAGE = """<html><body><main><article><div class="post-layout">
<div class="post-content">
<header><div><img src="/authors/someone.png"></div>
<time class="date mb-5">June 12, 2025</time>
<h1 class="m-0">Example outage on June 12, 2025</h1></header>
<div class="article-content">
<p>On June 12, 2025, requests failed.</p>
<h2>Timeline</h2><p>All times UTC.</p>
<figure><img src="images/chart.png" alt="chart"></figure>
<img src="https://cf-assets.example.com/diagram.png">
</div></div></div>
<section class="related"><img src="/related/card.png"></section>
</article></main></body></html>
"""


def doc(**changes) -> LibraryDocument:
    values = {
        "doc_id": "cloudflare-2025-06-12",
        "provider": "Cloudflare",
        "title": "Example outage on June 12, 2025",
        "url": URL,
        "published_at": "2025-06-12",
        "filename": "cloudflare-2025-06-12.html",
        "sha256": "a" * 64,
        "retrieved_at": "2026-10-27T15:58:00Z",
        "licence": "Copyright Cloudflare; not redistributed",
        "attribution": "Cloudflare blog",
        "kind": "same-provider",
        "serves": ("case-2026",),
        "reason": "r",
    }
    return LibraryDocument(**values | changes)


CASES = {"case-2026": Case("case-2026", "t", "Cloudflare", "showcase", "2026-02-20T18:45:16Z", ())}


@pytest.mark.parametrize("dated", ["2026-02-21", "February 21, 2026", "21 February 2026"])
def test_paragraph_dated_after_the_cutoff_is_dropped_and_listed(dated):
    markdown = f"# Title\n\nKept before.\n\nOn {dated} we changed the rollout.\n\nKept after.\n"

    sections, dropped = cut_later_text(markdown, "2026-02-20T18:45:16Z", "d")

    assert "changed the rollout" not in sections[0].markdown
    assert "Kept before." in sections[0].markdown and "Kept after." in sections[0].markdown
    assert len(dropped) == 1 and "2026-02-21" in dropped[0]


def test_undated_update_note_is_dropped():
    markdown = "# Title\n\nBody.\n\n**Update:** we have since rolled back.\n\nUpdate: more.\n"

    sections, dropped = cut_later_text(markdown, "2026-02-20T18:45:16Z", "d")

    assert sections[0].markdown.strip() == "# Title\n\nBody."
    assert len(dropped) == 2


def test_text_dated_before_the_cutoff_is_kept():
    markdown = "# Title\n\nOn 2026-02-20 at 09:00 and on February 19, 2026, things failed.\n"

    sections, dropped = cut_later_text(markdown, "2026-02-20T18:45:16Z", "d")

    assert "things failed" in sections[0].markdown
    assert dropped == []


def test_sections_follow_heading_order_with_stable_ids():
    markdown = "Intro.\n\n# Title\n\nA.\n\n## Impact\n\nB.\n\n### Detail\n\nC.\n"

    sections, _ = cut_later_text(markdown, "2026-02-20T18:45:16Z", "cloudflare-2025-06-12")

    assert [s.section_id for s in sections] == [
        f"lib/cloudflare-2025-06-12/s{n}" for n in (1, 2, 3, 4)
    ]
    assert [s.heading for s in sections] == ["", "Title", "Impact", "Detail"]
    assert sections == cut_later_text(markdown, "2026-02-20T18:45:16Z", "cloudflare-2025-06-12")[0]


def test_article_keeps_title_date_and_body_only():
    found = article(PAGE.encode(), URL)

    assert found.title == "Example outage on June 12, 2025"
    assert (found.date_text, found.published_at) == ("June 12, 2025", "2025-06-12")
    assert "requests failed" in found.html and "related" not in found.html


def test_images_outside_the_article_are_ignored():
    sources = figure_sources(PAGE.encode(), URL)

    assert not any("authors" in s or "related" in s for s in sources)
    assert len(sources) == 2


def test_relative_image_paths_resolve_against_the_page():
    assert figure_sources(PAGE.encode(), URL) == [
        "https://blog.cloudflare.com/example-outage/images/chart.png",
        "https://cf-assets.example.com/diagram.png",
    ]


def test_a_page_without_its_article_body_is_refused():
    page = PAGE.replace('class="article-content"', 'class="other"')

    with pytest.raises(ValueError, match="article"):
        article(page.encode(), URL)


def test_a_site_without_rules_is_refused():
    with pytest.raises(ValueError, match="example.org"):
        article(PAGE.encode(), "https://example.org/post")


@pytest.mark.parametrize(
    ("text", "iso"),
    [
        ("June 12, 2025", "2025-06-12"),
        ("December 10th, 2021", "2021-12-10"),
        ("Oct 12, 2018", "2018-10-12"),
        ("13 Jun 2025", "2025-06-13"),
        ("2016-02-03", "2016-02-03"),
    ],
)
def test_page_dates_in_each_site_format(text, iso):
    assert page_date(text) == iso


def test_library_figures_are_never_displayable():
    assert display_allowed("CC BY 4.0")
    assert not display_allowed("Copyright Cloudflare; not redistributed")
    assert not display_allowed("CC BY-NC 4.0")


PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


class FakeAnalyzer:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def __call__(self, analyzer_id, data, mime):
        self.calls.append((analyzer_id, mime))
        if analyzer_id == "hindcast_postmortem":
            content = {"markdown": "# Example outage\n\nBody.\n\n## Timeline\n\nAll times UTC.\n"}
        else:
            content = {
                "fields": {
                    "description": {"valueString": "A line chart."},
                    "alt_text": {"valueString": "Line chart."},
                    "text_in_image": {"valueString": "Requests"},
                }
            }
        return {"result": {"contents": [content]}, "usage": {"tokens": {"gpt-5-mini-input": 10}}}


def test_published_date_must_match_the_registry():
    with pytest.raises(ValueError, match="2025-06-11"):
        extract_document(
            doc(published_at="2025-06-11"), CASES, PAGE.encode(), FakeAnalyzer(), lambda u: PNG
        )


def test_extract_document_describes_each_figure_and_never_displays_it():
    analyzer = FakeAnalyzer()

    extracted, usage = extract_document(doc(), CASES, PAGE.encode(), analyzer, lambda u: PNG)

    assert [s.heading for s in extracted.sections] == ["Example outage", "Timeline"]
    assert [f.figure_id for f in extracted.figures] == [
        "lib/cloudflare-2025-06-12/fig1",
        "lib/cloudflare-2025-06-12/fig2",
    ]
    assert all(f.display is False and f.description == "A line chart." for f in extracted.figures)
    assert analyzer.calls[0] == ("hindcast_postmortem", "text/html")
    assert analyzer.calls[1:] == [("hindcast_chart", "image/png")] * 2
    assert usage["tokens"]["gpt-5-mini-input"] == 30
    assert json.loads(extracted.to_json())["doc_id"] == "cloudflare-2025-06-12"


def test_a_figure_in_a_format_the_service_cannot_read_is_listed_not_sent():
    analyzer = FakeAnalyzer()

    extracted, _ = extract_document(doc(), CASES, PAGE.encode(), analyzer, lambda u: b"<svg/>")

    assert extracted.figures == ()
    assert len([d for d in extracted.dropped if "image type" in d]) == 2
    assert analyzer.calls == [("hindcast_postmortem", "text/html")]


def test_section_is_a_plain_record():
    assert Section("lib/d/s1", "H", "x") == Section("lib/d/s1", "H", "x")


def test_a_body_the_page_repeats_whole_is_kept_once():
    # As on the AWS page: the repeat differs in markup and ends with a link.
    once = (
        "<p><b>December 10th, 2021</b></p><p>We want to provide details. " + "x" * 200 + "</p>"
        "<p>In closing, we apologise.{br}</p>"
    )
    page = (
        '<html><body><div data-eb-item-id="ams#c1"><h2 data-rg-n="HeadingText">Summary of the event'
        '</h2><div data-rg-n="BodyText">'
        + once.format(br="<br>")
        + once.format(br="")
        + '<p><a href="/pes/">Back</a></p></div></div></body></html>'
    )

    found = article(page.encode(), "https://aws.amazon.com/message/12721/")

    assert found.html.count("We want to provide details.") == 1
    assert "In closing" in found.html and "Back" not in found.html
    assert (found.title, found.published_at) == ("Summary of the event", "2021-12-10")


def test_two_identical_short_paragraphs_do_not_cut_the_body():
    short = "<p><b>December 10th, 2021</b></p><p>Retry.</p><p>Retry.</p>"
    page = (
        '<html><body><div data-eb-item-id="ams#c1"><h2 data-rg-n="HeadingText">T</h2>'
        f'<div data-rg-n="BodyText">{short}{short}<p>Tail.</p></div></div></body></html>'
    )

    assert "Tail." in article(page.encode(), "https://aws.amazon.com/message/1/").html


def test_github_body_leaves_out_tags_and_the_author_bio():
    page = (
        '<html><body><main><header><h1 class="h3-mktg">Availability report</h1></header>'
        '<section class="container-xl">'
        '<time class="d-block" datetime="2026-07-08">July 8, 2026</time></section>'
        '<div><section class="col-12 col-md-8"><p>On June 10, requests failed.</p>'
        '<section class="my-6"><ul><li>Tags: availability report</li></ul></section>'
        '<div class="mt-8"><h2>Written by</h2></div>'
        '<div class="mt-8"><article class="author-bio"><header>Some Author</header>'
        "<p>Engineer.</p></article></div></section></div></main></body></html>"
    )

    found = article(page.encode(), "https://github.blog/news-insights/company-news/x/")

    assert "requests failed" in found.html
    assert "Some Author" not in found.html and "Tags:" not in found.html
    assert "Written by" not in found.html
    assert found.published_at == "2026-07-08"


def test_github_incident_lines_in_bold_become_headings():
    page = (
        "<html><body><main><header><h1>Availability report</h1></header>"
        '<section><time class="d-block" datetime="2026-07-08">July 8, 2026</time></section>'
        '<div><section class="col-12 col-md-8"><p><strong>The short version:</strong> fine.</p>'
        "<p><strong>June 04 17:30 UTC (lasting 1 hour and 25 minutes)</strong></p><p>First.</p>"
        "<p><strong>June 10 15:05 UTC (lasting 55 minutes)</strong></p><p>Second.</p>"
        "</section></div></main></body></html>"
    )

    body = article(page.encode(), "https://github.blog/news-insights/company-news/x/").html

    assert "<h3>June 04 17:30 UTC (lasting 1 hour and 25 minutes)</h3>" in body
    assert "<h3>June 10 15:05 UTC (lasting 55 minutes)</h3>" in body
    assert "<strong>The short version:</strong>" in body
