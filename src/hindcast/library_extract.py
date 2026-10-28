"""Library extraction: each captured page's article, its sections, and its charts.

Content Understanding turns a whole HTML page into markdown, navigation and
related posts included, so the article is cut out of the page first, by a
fixed rule per site. A page whose title, date, or body the rule cannot find
is refused, not guessed. The page's own date must equal the registry's.

Inside the article, text dated after the earliest case the document serves,
and undated update notes, are dropped and listed (decision 0013). Each image
in the article is fetched and described; library images are never shown,
because their licence does not allow it.
"""

import hashlib
import html
import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from hindcast.cases import Case
from hindcast.library import LibraryDocument, cutoff

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}


@dataclass(frozen=True)
class Section:
    section_id: str
    heading: str
    markdown: str


@dataclass(frozen=True)
class Figure:
    figure_id: str
    source_url: str
    sha256: str
    description: str
    alt_text: str
    text_in_image: str
    display: bool


@dataclass(frozen=True)
class ExtractedDocument:
    doc_id: str
    published_at: str
    sections: tuple[Section, ...]
    figures: tuple[Figure, ...]
    dropped: tuple[str, ...]

    def to_json(self) -> bytes:
        return (json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n").encode()


@dataclass(frozen=True)
class Article:
    title: str
    date_text: str
    published_at: str
    html: str
    figures: tuple[str, ...]


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str]
    start: str = ""
    children: list = field(default_factory=list)

    def classes(self) -> list[str]:
        return self.attrs.get("class", "").split()


class _Tree(HTMLParser):
    """A small element tree that keeps the page's own markup for re-serialising."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.root = _Node("root", {})
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag, {k: v or "" for k, v in attrs}, self.get_starttag_text() or "")
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag, {k: v or "" for k, v in attrs}, self.get_starttag_text() or "")
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag: str) -> None:
        # Close the nearest open element of this tag; stray end tags are ignored.
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)

    def handle_entityref(self, name: str) -> None:
        self.stack[-1].children.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.stack[-1].children.append(f"&#{name};")


def _parse(page: bytes) -> _Node:
    tree = _Tree()
    tree.feed(page.decode("utf-8", errors="replace"))
    return tree.root


def _all(node: _Node, match: Callable[[_Node], bool]):
    for child in node.children:
        if isinstance(child, _Node):
            if match(child):
                yield child
            yield from _all(child, match)


def _first(node: _Node | None, match: Callable[[_Node], bool]) -> _Node | None:
    return None if node is None else next(_all(node, match), None)


def _text(node: _Node) -> str:
    parts = [c if isinstance(c, str) else _text(c) for c in node.children]
    return re.sub(r"\s+", " ", html.unescape("".join(parts))).strip()


def _html(node: _Node) -> str:
    inner = "".join(c if isinstance(c, str) else _html(c) for c in node.children)
    return node.start + ("" if node.tag in VOID else f"{inner}</{node.tag}>")


def _without(node: _Node, drop: Callable[[_Node], bool]) -> _Node:
    """A copy of node with every descendant that drop matches left out."""
    children = [
        c if isinstance(c, str) else _without(c, drop)
        for c in node.children
        if isinstance(c, str) or not drop(c)
    ]
    return _Node(node.tag, node.attrs, node.start, children)


def _has_class(name: str) -> Callable[[_Node], bool]:
    return lambda n: name in n.classes()


def page_date(text: str) -> str:
    """A date as a page states it, as YYYY-MM-DD."""
    cleaned = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", text.strip())
    for form in ("%B %d, %Y", "%b %d, %Y", "%d %b %Y", "%d %B %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, form).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"{text!r} is not a date in a known form")


def _cloudflare(root: _Node) -> tuple[_Node | None, _Node | None, _Node | None]:
    post = _first(root, _has_class("post-content"))
    header = _first(post, lambda n: n.tag == "header")
    return (
        _first(header, lambda n: n.tag == "h1"),
        _first(header, lambda n: n.tag == "time" and "date" in n.classes()),
        _first(post, _has_class("article-content")),
    )


def _github(root: _Node) -> tuple[_Node | None, _Node | None, _Node | None]:
    main = _first(root, lambda n: n.tag == "main")
    # The first time element is the publish date; a second one is "Updated ...".
    when = _first(main, lambda n: n.tag == "time" and "datetime" in n.attrs)
    body = _first(main, lambda n: n.tag == "section" and "col-md-8" in n.classes())
    if body is not None:
        # The post's tags and its author's bio close the body; neither is the
        # article, and the bio names a person.
        body = _without(
            body,
            lambda n: (
                "author-bio" in n.classes()
                or (n.tag in ("section", "div") and _text(n).startswith(("Tags", "Written by")))
            ),
        )
    return _first(main, lambda n: n.tag == "h1"), when, body


def _aws(root: _Node) -> tuple[_Node | None, _Node | None, _Node | None]:
    # The page has many BodyText blocks (menus too); the summary is the one in
    # the content item.
    item = _first(root, lambda n: "data-eb-item-id" in n.attrs)
    body = _first(item, lambda n: n.attrs.get("data-rg-n") == "BodyText")
    return (
        _first(root, lambda n: n.attrs.get("data-rg-n") == "HeadingText"),
        _first(body, lambda n: n.tag == "b"),
        body,
    )


def _google(root: _Node) -> tuple[_Node | None, _Node | None, _Node | None]:
    def update_date(n: _Node) -> bool:
        # A row's date cell: td in the older pages, th in the newer; the header says "Date".
        return n.tag in ("td", "th") and "date" in n.classes() and _text(n) != "Date"

    table = _first(root, lambda n: n.tag == "table" and _first(n, update_date) is not None)
    # Updates are listed newest first: the page reached its captured form on
    # the first row's date, which is later than or equal to the report's.
    newest = _first(table, update_date)
    title = _first(root, lambda n: n.tag == "h2" and "incident-description" in n.classes())
    if title is None:
        title = _first(
            root, lambda n: n.tag == "h1" and "page-header" not in n.classes() and _text(n) != ""
        )
    return title, newest, table


# GitHub's monthly reports mark some incidents with a bold line, not a heading.
GITHUB_INCIDENT = re.compile(
    r"<p[^>]*>\s*<strong>((?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December) \d{1,2} \d{2}:\d{2} UTC[^<]*)</strong>\s*</p>"
)

SITES = {
    "blog.cloudflare.com": _cloudflare,
    "github.blog": _github,
    "aws.amazon.com": _aws,
    "status.cloud.google.com": _google,
}


def _once(body: _Node) -> str:
    """The body's markup, cut to its first copy if the page repeats it.

    The copies are compared by text, since a repeat can differ in markup (a
    stray <br>), and the repeated run has to be substantial, so two identical
    short paragraphs do not cut a body down.
    """
    parts = [c for c in body.children if not (isinstance(c, str) and not c.strip())]
    texts = [p.strip() if isinstance(p, str) else _text(p) for p in parts]
    for k in range(3, len(parts) // 2 + 1):
        if texts[0] and texts[k : 2 * k] == texts[:k] and sum(map(len, texts[:k])) >= 200:
            return "".join(p if isinstance(p, str) else _html(p) for p in parts[:k])
    return _html(body)


def article(page: bytes, url: str) -> Article:
    """The page's title, publish date, and article body, found by the site's rule."""
    host = urlparse(url).hostname or ""
    if host not in SITES:
        raise ValueError(f"no article rule for {host}")
    title, when, body = SITES[host](_parse(page))
    if title is None or when is None or body is None:
        missing = [
            name
            for name, node in (("title", title), ("date", when), ("article", body))
            if node is None
        ]
        raise ValueError(f"{url}: no {', '.join(missing)} found by the {host} rule")
    date_text = (
        when.attrs.get("datetime", "")[:10]
        if when.tag == "time" and host == "github.blog"
        else _text(when)
    )
    body_html = _once(body)
    if host == "github.blog":
        # Each incident becomes its own section, as with a heading.
        body_html = GITHUB_INCIDENT.sub(r"<h3>\1</h3>", body_html)
    images = [
        urljoin(url, n.attrs["src"])
        for n in _all(_parse(body_html.encode()), lambda n: n.tag == "img" and "src" in n.attrs)
        if not n.attrs["src"].startswith("data:")
    ]
    return Article(
        title=_text(title),
        date_text=date_text,
        published_at=page_date(date_text),
        html=body_html,
        figures=tuple(dict.fromkeys(images)),
    )


def figure_sources(page: bytes, page_url: str) -> list[str]:
    return list(article(page, page_url).figures)


def display_allowed(licence: str) -> bool:
    """Only an image under a licence that allows showing it is displayed."""
    return licence == "CC BY 4.0"


MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATES = [
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
    re.compile(rf"\b((?:{MONTHS}) \d{{1,2}}(?:st|nd|rd|th)?, \d{{4}})\b"),
    re.compile(rf"\b(\d{{1,2}} (?:{MONTHS}) \d{{4}})\b"),
]
UPDATE_NOTE = re.compile(r"^[*_\s]*(update|updated|edit|editor's note)\b[^:\n]{0,40}:", re.I)


def _dates(text: str) -> list[str]:
    found = []
    for pattern in DATES:
        for match in pattern.findall(text):
            try:
                found.append(page_date(match))
            except ValueError:
                continue
    return found


def cut_later_text(markdown: str, cutoff: str, doc_id: str) -> tuple[list[Section], list[str]]:
    """Sections by heading, without paragraphs dated after cutoff or undated update notes."""
    limit = date.fromisoformat(cutoff[:10])
    sections: list[tuple[str, list[str]]] = [("", [])]
    dropped: list[str] = []
    for block in re.split(r"\n\s*\n", markdown.strip()):
        heading = re.match(r"^(#{1,6})\s+(.*)", block)
        if heading and "\n" not in block.strip():
            sections.append((heading.group(2).strip(), [block.strip()]))
            continue
        # The cutoff day itself counts as later: a date cannot be ordered against
        # the case's start time, as the registry also refuses.
        later = [d for d in _dates(block) if date.fromisoformat(d) >= limit]
        where = sections[-1][0] or "(start)"
        if later:
            dropped.append(f"{where}: a paragraph dated {later[0]}, on or after {cutoff[:10]}")
        elif UPDATE_NOTE.match(block) and not _dates(block):
            dropped.append(f"{where}: an undated update note")
        else:
            sections[-1][1].append(block.strip())
    kept = [(h, blocks) for h, blocks in sections if any(not b.startswith("#") for b in blocks)]
    return [
        Section(f"lib/{doc_id}/s{n}", heading, "\n\n".join(blocks))
        for n, (heading, blocks) in enumerate(kept, 1)
    ], dropped


def image_mime(data: bytes) -> str | None:
    """Image types the service reads; anything else (SVG included) is not sent."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def field_value(content: dict, name: str) -> str:
    return (content.get("fields", {}).get(name) or {}).get("valueString") or ""


def add_usage(total: dict, usage: dict) -> None:
    """Sum usage counters, nested ones (tokens per model) included."""
    for key, value in usage.items():
        if isinstance(value, dict):
            add_usage(total.setdefault(key, {}), value)
        elif isinstance(value, int | float):
            total[key] = total.get(key, 0) + value


def extract_document(
    doc: LibraryDocument,
    cases: dict[str, Case],
    page: bytes,
    analyzer: Callable[[str, bytes, str], dict],
    fetch: Callable[[str], bytes],
) -> tuple[ExtractedDocument, dict]:
    """Extract one library page; returns the document and the usage it cost."""
    found = article(page, doc.url)
    if found.published_at != doc.published_at:
        raise ValueError(
            f"{doc.doc_id}: the page says {found.published_at}, the registry {doc.published_at}"
        )
    usage: dict = {}
    # The page's own title and date stay with the article, so the analyzer
    # reads them as the page states them.
    wrapped = (
        f"<html><body><h1>{html.escape(found.title)}</h1><p>{html.escape(found.date_text)}</p>"
        f"{found.html}</body></html>"
    )
    result = analyzer("hindcast_postmortem", wrapped.encode(), "text/html")
    add_usage(usage, result["usage"])
    sections, dropped = cut_later_text(
        result["result"]["contents"][0].get("markdown", ""), cutoff(doc, cases), doc.doc_id
    )
    if not sections:
        raise ValueError(f"{doc.doc_id}: no text left after the cut")
    figures = []
    for source in found.figures:
        data = fetch(source)
        mime = image_mime(data)
        if mime is None:
            dropped.append(f"figure {source}: image type not read by the service")
            continue
        described = analyzer("hindcast_chart", data, mime)
        add_usage(usage, described["usage"])
        content = described["result"]["contents"][0]
        figures.append(
            Figure(
                figure_id=f"lib/{doc.doc_id}/fig{len(figures) + 1}",
                source_url=source,
                sha256=hashlib.sha256(data).hexdigest(),
                description=field_value(content, "description"),
                alt_text=field_value(content, "alt_text"),
                text_in_image=field_value(content, "text_in_image"),
                display=display_allowed(doc.licence),
            )
        )
    return (
        ExtractedDocument(
            doc.doc_id, doc.published_at, tuple(sections), tuple(figures), tuple(dropped)
        ),
        usage,
    )
