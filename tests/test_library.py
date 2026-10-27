import re
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from hindcast.cases import Case, SourceFile, load_cases
from hindcast.evidence import cut
from hindcast.library import cutoff, load_library

LIBRARY = Path("data/library.yaml")
TAG = re.compile(r"(product|symptom|scale): \S.*")


def symptoms() -> dict[str, list[dict]]:
    return YAML(typ="safe", pure=True).load(LIBRARY)["symptoms"]


def test_every_case_has_tagged_symptoms():
    cases = load_cases()
    tagged = symptoms()

    assert sorted(tagged) == sorted(cases)
    for case_id, tags in tagged.items():
        assert tags, case_id
        for tag in tags:
            assert sorted(tag) == ["quote", "tag", "update_id"], (case_id, tag)
            assert TAG.fullmatch(tag["tag"]), (case_id, tag["tag"])
            assert tag["quote"].strip(), (case_id, tag["tag"])
            assert tag["update_id"].startswith(f"{case_id}/u"), (case_id, tag["update_id"])


def test_symptom_quotes_appear_in_their_update():
    # Picks rest on what the live updates showed, so every tag has to quote the
    # cut evidence word for word, never the postmortem.
    checked = 0
    for case in load_cases().values():
        status = next(s for s in case.sources if s.kind == "status-updates")
        path = Path("data/sources") / case.case_id / status.filename
        if not path.is_file():
            continue
        updates = {u.update_id: u.text for u in cut(case, path.read_bytes()).updates}
        for tag in symptoms()[case.case_id]:
            # A bool, so a failure names the tag without printing the update.
            text = updates.get(tag["update_id"])
            found = text is not None and tag["quote"] in text
            assert found, (tag["update_id"], tag["quote"])
            checked += 1
    if not checked:
        pytest.skip("no local status snapshots under data/sources/")


CASE_SOURCE = SourceFile(
    doc_id="example-postmortem",
    filename="example-postmortem.html",
    url="https://blog.cloudflare.com/example-outage/",
    licence="Copyright Cloudflare; not redistributed",
    attribution="Cloudflare blog",
    sha256="0" * 64,
    retrieved_at="2026-10-26T08:00:00Z",
    kind="postmortem",
)
CASES = {
    "example-2026": Case(
        "example-2026",
        "Elevated errors",
        "Cloudflare",
        "showcase",
        "2026-02-20T18:45:16Z",
        (CASE_SOURCE,),
    ),
    "later-2026": Case(
        "later-2026", "Slow pages", "GitHub", "showcase", "2026-08-17T13:40:03Z", (CASE_SOURCE,)
    ),
}
DOCUMENT = """\
  - doc_id: aws-2025-10-20
    provider: AWS
    title: Summary of the service disruption in us-east-1
    url: https://aws.amazon.com/message/101925/
    published_at: "2025-10-23"
    filename: aws-2025-10-20.html
    sha256: "{sha256}"
    retrieved_at: "{retrieved_at}"
    licence: Copyright Amazon; not redistributed
    attribution: AWS post-event summary
    kind: other-provider
    serves: [example-2026]
    reason: 'Also "errors or timeouts reaching the network" across many services.'
"""
SYMPTOMS = """\
symptoms:
  example-2026:
    - tag: "symptom: errors or timeouts"
      quote: errors or timeouts reaching the network
      update_id: example-2026/u1
  later-2026:
    - tag: "symptom: elevated HTTP error rates"
      quote: high error rates
      update_id: later-2026/u8
documents:
"""


def library_file(tmp_path: Path, document: str = DOCUMENT, **values: str) -> Path:
    values = {"sha256": "a" * 64, "retrieved_at": "2026-10-27T09:00:00Z"} | values
    for name, value in values.items():
        document = document.replace("{" + name + "}", value)
    path = tmp_path / "library.yaml"
    path.write_text(SYMPTOMS + document, encoding="utf-8")
    return path


def test_load_library_reads_a_document(tmp_path):
    library = load_library(library_file(tmp_path), CASES)

    doc = library["aws-2025-10-20"]
    assert (doc.provider, doc.kind, doc.serves) == ("AWS", "other-provider", ("example-2026",))
    assert doc.published_at == "2025-10-23"
    assert cutoff(doc, CASES) == "2026-02-20T18:45:16Z"


@pytest.mark.parametrize(
    "published",
    ['""', '"2026-02-20"', '"2026-03-01"', '"23 October 2025"'],
    ids=["missing", "same-day-as-case", "after-case", "not-iso"],
)
def test_document_without_a_date_before_every_served_case_is_rejected(tmp_path, published):
    document = DOCUMENT.replace('"2025-10-23"', published)

    with pytest.raises(ValueError, match="aws-2025-10-20"):
        load_library(library_file(tmp_path, document), CASES)


def test_a_date_must_precede_every_served_case(tmp_path):
    # Before the later case but not the earlier one: still refused.
    document = (
        DOCUMENT.replace('"2025-10-23"', '"2026-05-01"')
        .replace("serves: [example-2026]", "serves: [later-2026, example-2026]")
        .replace('network" across', 'network" and "high error rates" across')
    )

    with pytest.raises(ValueError, match="aws-2025-10-20.*example-2026"):
        load_library(library_file(tmp_path, document), CASES)


def test_a_case_postmortem_cannot_be_a_library_document(tmp_path):
    document = DOCUMENT.replace(
        "https://aws.amazon.com/message/101925/", "https://blog.cloudflare.com/example-outage"
    )

    with pytest.raises(ValueError, match="case source"):
        load_library(library_file(tmp_path, document), CASES)


def test_doc_ids_are_unique_across_cases_and_library(tmp_path):
    with pytest.raises(ValueError, match="appears twice"):
        load_library(library_file(tmp_path, DOCUMENT + DOCUMENT), CASES)
    clash = DOCUMENT.replace("doc_id: aws-2025-10-20", "doc_id: example-postmortem")
    with pytest.raises(ValueError, match="example-postmortem"):
        load_library(library_file(tmp_path, clash), CASES)


def test_serves_must_name_known_cases(tmp_path):
    for serves in ("serves: [missing-2026]", "serves: []"):
        document = DOCUMENT.replace("serves: [example-2026]", serves)
        with pytest.raises(ValueError, match="serves"):
            load_library(library_file(tmp_path, document), CASES)


def test_reason_must_quote_a_tagged_symptom(tmp_path):
    document = DOCUMENT.replace(
        "reason: 'Also \"errors or timeouts reaching the network\" across many services.'",
        "reason: Same root cause as the case.",
    )

    with pytest.raises(ValueError, match="reason"):
        load_library(library_file(tmp_path, document), CASES)


def test_empty_hash_is_accepted_only_in_draft_mode(tmp_path):
    path = library_file(tmp_path, sha256="", retrieved_at="")

    assert load_library(path, CASES, draft=True)["aws-2025-10-20"].sha256 == ""
    with pytest.raises(ValueError, match="sha256"):
        load_library(path, CASES)
    with pytest.raises(ValueError, match="retrieved_at"):
        load_library(library_file(tmp_path, retrieved_at=""), CASES)


def test_the_committed_library_loads_with_every_hash_pinned():
    assert load_library(LIBRARY, load_cases())
