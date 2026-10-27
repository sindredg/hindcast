import hashlib
import json

import pytest
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

from hindcast import ingest
from hindcast.cases import Case, SourceFile
from hindcast.evidence import cut, evidence_json
from hindcast.ingest import (
    EvidenceDiffers,
    describe_chart,
    ingest_evidence,
    ingest_library,
    library_summary,
    summary,
)
from hindcast.library import LibraryDocument
from hindcast.storage import SourceMismatch

PLANTED_CAUSE = "The cause was a planted sentence."
SNAPSHOT = json.dumps(
    {
        "name": "Elevated errors",
        "started_at": "2026-02-20T18:45:16.965Z",
        "incident_updates": [
            {"created_at": "2026-02-20T18:45:16Z", "status": "investigating", "body": "Errors."},
            {"created_at": "2026-02-20T19:00:00Z", "status": "postmortem", "body": PLANTED_CAUSE},
            {"created_at": "2026-02-20T23:50:58Z", "status": "resolved", "body": PLANTED_CAUSE},
        ],
    }
).encode()

LIB_PAGE = (
    b'<html><body><div class="post-content"><header><time class="date">June 12, 2025</time>'
    b'<h1>Example outage</h1></header><div class="article-content"><p>Body.</p></div></div>'
    b"</body></html>"
)


def case(snapshot: bytes = SNAPSHOT) -> Case:
    status = SourceFile(
        doc_id="cloudflare-status-2026-02-20",
        filename="cloudflare-status-2026-02-20.json",
        url="https://www.cloudflarestatus.com/api/v2/incidents/kwy3dt82bwbt.json",
        licence="Copyright Cloudflare; not redistributed",
        attribution="Cloudflare",
        sha256=hashlib.sha256(snapshot).hexdigest(),
        retrieved_at="2026-10-25T21:09:30Z",
        kind="status-updates",
    )
    return Case(
        "cloudflare-2026-02-20",
        "Elevated errors",
        "Cloudflare",
        "development",
        "2026-02-20T18:45:16Z",
        (status,),
    )


class FakeBlob:
    def __init__(self, data: bytes):
        self.data = data

    def readall(self) -> bytes:
        return self.data


class FakeContainer:
    """Serves `data` for any blob; holds `existing` blobs, which an upload keeps unless told."""

    def __init__(self, data: bytes = b"", existing: dict[str, bytes] | None = None):
        self.data = data
        self.existing = existing or {}
        self.uploaded: list[tuple[str, bytes, bool]] = []

    def download_blob(self, name: str) -> FakeBlob:
        if name not in self.existing and not self.data:
            raise ResourceNotFoundError("no such blob")
        return FakeBlob(self.existing.get(name, self.data))

    def upload_blob(self, name: str, data: bytes, overwrite: bool = False) -> None:
        if name in self.existing and not overwrite:
            raise ResourceExistsError("exists")
        self.uploaded.append((name, data, overwrite))


def test_ingest_writes_the_cut_evidence_locally_and_to_blob(tmp_path):
    sources, extracted = FakeContainer(SNAPSHOT), FakeContainer()

    _, status = ingest_evidence(case(), out_dir=tmp_path, client=sources, uploader=extracted)

    assert status == "uploaded"
    local = (tmp_path / "cloudflare-2026-02-20.json").read_bytes()
    assert local == evidence_json(cut(case(), SNAPSHOT))
    assert extracted.uploaded == [("evidence/cloudflare-2026-02-20.json", local, False)]


def test_ingest_writes_nothing_when_a_source_fails_its_hash(tmp_path):
    tampered = FakeContainer(SNAPSHOT.replace(b"Errors.", b"Errors!"))
    extracted = FakeContainer()

    with pytest.raises(SourceMismatch):
        ingest_evidence(case(), out_dir=tmp_path, client=tampered, uploader=extracted)

    assert list(tmp_path.iterdir()) == []
    assert extracted.uploaded == []


def test_ingest_prints_counts_not_text():
    lines = summary(cut(case(), SNAPSHOT))

    assert lines[0] == "cloudflare-2026-02-20: 2 updates (resolved 2026-02-20T23:50:58Z), dropped 1"
    assert lines[1:] == ["  report: 1"]
    assert not any(PLANTED_CAUSE in line or "Errors." in line for line in lines)


BLOB = "evidence/cloudflare-2026-02-20.json"


def test_existing_identical_evidence_writes_the_local_copy(tmp_path):
    same = evidence_json(cut(case(), SNAPSHOT))
    extracted = FakeContainer(existing={BLOB: same})

    _, status = ingest_evidence(
        case(), out_dir=tmp_path, client=FakeContainer(SNAPSHOT), uploader=extracted
    )

    assert status == "unchanged"
    assert (tmp_path / "cloudflare-2026-02-20.json").read_bytes() == same
    assert extracted.uploaded == []


def test_existing_different_evidence_is_kept_and_reported(tmp_path):
    extracted = FakeContainer(existing={BLOB: b"{}\n"})

    with pytest.raises(EvidenceDiffers, match="cloudflare-2026-02-20"):
        ingest_evidence(
            case(), out_dir=tmp_path, client=FakeContainer(SNAPSHOT), uploader=extracted
        )

    assert list(tmp_path.iterdir()) == []
    assert extracted.uploaded == []


def test_main_reports_each_failing_case_and_exits_1(monkeypatch, capsys):
    good, bad = (
        case(),
        Case(
            "broken-case", "t", "Cloudflare", "development", "2026-02-20T18:45:16Z", case().sources
        ),
    )
    monkeypatch.setattr(ingest, "load_cases", lambda: {"broken-case": bad, good.case_id: good})

    def fake_ingest(c, *, replace):
        if c.case_id == "broken-case":
            raise ValueError("broken-case: no update marks the incident resolved")
        return cut(good, SNAPSHOT), "uploaded"

    monkeypatch.setattr(ingest, "ingest_evidence", fake_ingest)

    assert ingest.main(["evidence"]) == 1
    out = capsys.readouterr().out
    assert "broken-case: no update marks the incident resolved" in out
    assert "cloudflare-2026-02-20: 2 updates" in out
    assert "  blob: uploaded" in out


LIB_DOC = LibraryDocument(
    doc_id="cloudflare-2025-06-12",
    provider="Cloudflare",
    title="Example outage",
    url="https://blog.cloudflare.com/example-outage/",
    published_at="2025-06-12",
    filename="cloudflare-2025-06-12.html",
    sha256=hashlib.sha256(LIB_PAGE).hexdigest(),
    retrieved_at="2026-10-27T15:58:00Z",
    licence="Copyright Cloudflare; not redistributed",
    attribution="Cloudflare blog",
    kind="same-provider",
    serves=("cloudflare-2026-02-20",),
    reason="r",
)
LIB_CASES = {"cloudflare-2026-02-20": case()}


def fake_analyzer(calls: list):
    def analyzer(analyzer_id, data, mime):
        calls.append(analyzer_id)
        return {
            "result": {"contents": [{"markdown": "# Example outage\n\nBody.\n"}]},
            "usage": {"contextualizationTokens": 1000},
        }

    return analyzer


def test_library_writes_the_extract_locally_and_to_blob(tmp_path):
    calls, extracted = [], FakeContainer()

    data, status, usage = ingest_library(
        LIB_DOC,
        LIB_CASES,
        out_dir=tmp_path,
        client=FakeContainer(LIB_PAGE),
        uploader=extracted,
        analyzer=fake_analyzer(calls),
        fetch=lambda url: b"",
    )

    assert status == "uploaded" and calls == ["hindcast_postmortem"]
    assert (tmp_path / "cloudflare-2025-06-12.json").read_bytes() == data
    assert extracted.uploaded == [("library/cloudflare-2025-06-12.json", data, False)]
    assert json.loads(data)["sections"][0]["section_id"] == "lib/cloudflare-2025-06-12/s1"
    assert usage == {"contextualizationTokens": 1000}


def test_library_extract_already_in_blob_is_reused_without_calling_the_service(tmp_path):
    calls = []
    extracted = FakeContainer(existing={"library/cloudflare-2025-06-12.json": b'{"kept": 1}\n'})

    data, status, usage = ingest_library(
        LIB_DOC,
        LIB_CASES,
        out_dir=tmp_path,
        client=FakeContainer(LIB_PAGE),
        uploader=extracted,
        analyzer=fake_analyzer(calls),
        fetch=lambda url: b"",
    )

    assert (status, calls, usage) == ("reused", [], {})
    assert (tmp_path / "cloudflare-2025-06-12.json").read_bytes() == b'{"kept": 1}\n'


def test_library_summary_prints_counts_not_text():
    data = json.dumps(
        {"doc_id": "d", "sections": [{"markdown": PLANTED_CAUSE}], "figures": [], "dropped": ["x"]}
    ).encode()

    assert library_summary(data) == "d: 1 sections, 0 figures, dropped 1"


CHART_PNG = b"\x89PNG\r\n\x1a\n" + b"1" * 32


def chart_case() -> Case:
    chart = SourceFile(
        doc_id="cloudflare-radar-2026-02-20",
        filename="radar-routing.png",
        url="https://radar.cloudflare.com/routing/as13335",
        licence="CC BY 4.0",
        attribution="Cloudflare Radar",
        sha256=hashlib.sha256(CHART_PNG).hexdigest(),
        retrieved_at="2026-10-27T17:00:00Z",
        kind="chart",
    )
    base = case()
    return Case(
        base.case_id, base.title, base.provider, base.role, base.started_at, (*base.sources, chart)
    )


def chart_analyzer(calls: list):
    def analyzer(analyzer_id, data, mime):
        calls.append((analyzer_id, mime))
        fields = {
            "description": {"valueString": "A step chart of announced prefixes."},
            "alt_text": {"valueString": "Prefixes over time."},
            "text_in_image": {"valueString": "AS13335"},
        }
        return {"result": {"contents": [{"fields": fields}]}, "usage": {"tokens": {"x": 1}}}

    return analyzer


def test_a_chart_is_described_once_and_then_reused(tmp_path):
    charts = tmp_path / "charts" / "cloudflare-2026-02-20"
    charts.mkdir(parents=True)
    (charts / "radar-routing.png").write_bytes(CHART_PNG)
    chart = chart_case().sources[-1]
    calls, extracted = [], FakeContainer()

    data, status, _ = describe_chart(
        chart_case(),
        chart,
        charts_dir=tmp_path / "charts",
        out_dir=tmp_path / "out",
        uploader=extracted,
        analyzer=chart_analyzer(calls),
    )
    assert (status, calls) == ("uploaded", [("hindcast_chart", "image/png")])
    assert json.loads(data)["description"] == "A step chart of announced prefixes."

    extracted.existing = {name: blob for name, blob, _ in extracted.uploaded}
    _, again, _ = describe_chart(
        chart_case(),
        chart,
        charts_dir=tmp_path / "charts",
        out_dir=tmp_path / "out",
        uploader=extracted,
        analyzer=chart_analyzer(calls),
    )
    assert again == "reused" and len(calls) == 1


def test_a_chart_file_that_does_not_match_its_hash_is_refused(tmp_path):
    charts = tmp_path / "charts" / "cloudflare-2026-02-20"
    charts.mkdir(parents=True)
    (charts / "radar-routing.png").write_bytes(CHART_PNG + b"!")

    with pytest.raises(SourceMismatch, match="cloudflare-radar-2026-02-20"):
        describe_chart(
            chart_case(),
            chart_case().sources[-1],
            charts_dir=tmp_path / "charts",
            out_dir=tmp_path / "out",
            uploader=FakeContainer(),
            analyzer=chart_analyzer([]),
        )


def test_evidence_attaches_the_stored_chart_description(tmp_path):
    stored = json.dumps({"description": "A step chart.", "alt_text": "Prefixes."}).encode()
    extracted = FakeContainer(
        existing={"charts/cloudflare-2026-02-20/cloudflare-radar-2026-02-20.json": stored}
    )

    evidence, _ = ingest_evidence(
        chart_case(), out_dir=tmp_path, client=FakeContainer(SNAPSHOT), uploader=extracted
    )

    assert [(c.chart_id, c.description, c.display) for c in evidence.charts] == [
        ("cloudflare-2026-02-20/chart1", "A step chart.", True)
    ]


def test_evidence_refuses_a_chart_that_is_not_described_yet(tmp_path):
    with pytest.raises(ValueError, match="ingest charts"):
        ingest_evidence(
            chart_case(), out_dir=tmp_path, client=FakeContainer(SNAPSHOT), uploader=FakeContainer()
        )
    assert list(tmp_path.iterdir()) == []
