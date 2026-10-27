import re
from pathlib import Path

import pytest

from hindcast.cases import Case, SourceFile, load_cases, verify_local_files
from hindcast.evidence import cut

# sha256 of b"abc" (FIPS 180-2 test vector).
ABC_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

STATUS_SOURCE = """\
      - doc_id: example-status
        filename: example-status.json
        url: https://www.cloudflarestatus.com/api/v2/incidents/abc123def456.json
        licence: Copyright Cloudflare; not redistributed
        attribution: Cloudflare status page
        sha256: "{sha256}"
        retrieved_at: "2026-10-26T08:00:00Z"
        kind: status-updates
"""

POSTMORTEM_SOURCE = """\
      - doc_id: example-postmortem
        filename: example-postmortem.html
        url: https://blog.cloudflare.com/example-outage/
        licence: Copyright Cloudflare; not redistributed
        attribution: Cloudflare blog
        sha256: "{sha256}"
        retrieved_at: "2026-10-26T08:01:00Z"
        kind: postmortem
"""

ONE_CASE = (
    """\
cases:
  - case_id: example-2026
    title: Elevated errors across the network
    provider: Cloudflare
    role: showcase
    started_at: "2026-02-20T18:45:16Z"
    sources:
"""
    + STATUS_SOURCE
    + POSTMORTEM_SOURCE
)


def write_registry(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "cases.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def registry(sha256: str = ABC_SHA256) -> str:
    return ONE_CASE.replace("{sha256}", sha256)


def one_case(tmp_path: Path, sha256: str = ABC_SHA256) -> Case:
    return load_cases(write_registry(tmp_path, registry(sha256)))["example-2026"]


def test_load_cases_reads_case_and_sources(tmp_path):
    cases = load_cases(write_registry(tmp_path, registry()))

    assert cases == {
        "example-2026": Case(
            case_id="example-2026",
            title="Elevated errors across the network",
            provider="Cloudflare",
            role="showcase",
            started_at="2026-02-20T18:45:16Z",
            sources=(
                SourceFile(
                    doc_id="example-status",
                    filename="example-status.json",
                    url="https://www.cloudflarestatus.com/api/v2/incidents/abc123def456.json",
                    licence="Copyright Cloudflare; not redistributed",
                    attribution="Cloudflare status page",
                    sha256=ABC_SHA256,
                    retrieved_at="2026-10-26T08:00:00Z",
                    kind="status-updates",
                ),
                SourceFile(
                    doc_id="example-postmortem",
                    filename="example-postmortem.html",
                    url="https://blog.cloudflare.com/example-outage/",
                    licence="Copyright Cloudflare; not redistributed",
                    attribution="Cloudflare blog",
                    sha256=ABC_SHA256,
                    retrieved_at="2026-10-26T08:01:00Z",
                    kind="postmortem",
                ),
            ),
        )
    }


def test_load_cases_rejects_bad_case_id(tmp_path):
    text = registry().replace("example-2026", "Example 2026")

    with pytest.raises(ValueError, match="Example 2026"):
        load_cases(write_registry(tmp_path, text))


@pytest.mark.parametrize(
    ("field", "good", "bad"),
    [
        ("provider", "provider: Cloudflare", "provider: AWS"),
        ("role", "role: showcase", "role: demo"),
        ("kind", "kind: postmortem", "kind: report"),
    ],
)
def test_load_cases_rejects_unknown_choice(tmp_path, field, good, bad):
    text = registry().replace(good, bad)

    with pytest.raises(ValueError, match=field):
        load_cases(write_registry(tmp_path, text))


@pytest.mark.parametrize("bad", ["2026-10-26", "2026-10-26T10:00:00+02:00", "2026-10-26 08:00:00Z"])
def test_retrieved_at_must_be_utc_timestamp(tmp_path, bad):
    text = registry().replace('"2026-10-26T08:00:00Z"', f'"{bad}"')

    with pytest.raises(ValueError, match="retrieved_at"):
        load_cases(write_registry(tmp_path, text))


@pytest.mark.parametrize("bad", ["2025-11-18 11:48", "2026-02-20T18:45:16.965Z", "2026-02-20"])
def test_started_at_must_be_a_utc_timestamp(tmp_path, bad):
    text = registry().replace('"2026-02-20T18:45:16Z"', f'"{bad}"')

    with pytest.raises(ValueError, match=r"started_at '.+' must be a UTC time"):
        load_cases(write_registry(tmp_path, text))


def test_started_at_matches_the_cut_evidence():
    # The library's date bound and the prior-knowledge cutoff read started_at,
    # so it has to be the start the provider's own snapshot states.
    checked = 0
    for case in load_cases().values():
        status = next(s for s in case.sources if s.kind == "status-updates")
        path = Path("data/sources") / case.case_id / status.filename
        if path.is_file():
            assert case.started_at == cut(case, path.read_bytes()).started_at, case.case_id
            checked += 1
    if not checked:
        pytest.skip("no local status snapshots under data/sources/")


@pytest.mark.parametrize(
    ("role", "removed", "missing"),
    [
        ("showcase", POSTMORTEM_SOURCE, "postmortem"),
        ("development", POSTMORTEM_SOURCE, "postmortem"),
        ("showcase", STATUS_SOURCE, "status-updates"),
        ("injection", STATUS_SOURCE, "status-updates"),
    ],
    ids=["showcase-no-key", "development-no-key", "showcase-no-evidence", "injection-no-evidence"],
)
def test_case_needs_status_updates_and_postmortem(tmp_path, role, removed, missing):
    # The status updates are the evidence and the postmortem is the answer key;
    # an injection copy is never scored, so it needs no key.
    text = ONE_CASE.replace(removed, "").replace("role: showcase", f"role: {role}")

    with pytest.raises(ValueError, match=missing):
        load_cases(write_registry(tmp_path, text.replace("{sha256}", ABC_SHA256)))


def test_injection_case_loads_without_postmortem(tmp_path):
    text = ONE_CASE.replace(POSTMORTEM_SOURCE, "").replace("role: showcase", "role: injection")

    cases = load_cases(write_registry(tmp_path, text.replace("{sha256}", ABC_SHA256)))

    assert [s.kind for s in cases["example-2026"].sources] == ["status-updates"]


def test_load_cases_rejects_missing_field(tmp_path):
    text = registry().replace("        licence: Copyright Cloudflare; not redistributed\n", "", 1)

    with pytest.raises(ValueError, match="licence"):
        load_cases(write_registry(tmp_path, text))


def test_load_cases_rejects_a_case_without_sources(tmp_path):
    text = registry()[: registry().index("    sources:")]

    with pytest.raises(ValueError, match="sources"):
        load_cases(write_registry(tmp_path, text))


def test_load_cases_rejects_a_field_that_is_not_text(tmp_path):
    text = registry().replace("filename: example-status.json", "filename: [example-status.json]")

    with pytest.raises(ValueError, match="filename"):
        load_cases(write_registry(tmp_path, text))


def test_load_cases_rejects_a_doc_id_used_twice(tmp_path):
    case = registry()
    second = case.removeprefix("cases:\n").replace("example-2026", "other-2026")

    with pytest.raises(ValueError, match="example-status"):
        load_cases(write_registry(tmp_path, case + second))


@pytest.mark.parametrize("name", ["../outside.json", "sub/example.json", ".hidden.json"])
def test_load_cases_rejects_a_filename_that_is_not_a_plain_name(tmp_path, name):
    text = registry().replace("filename: example-status.json", f"filename: {name}")

    with pytest.raises(ValueError, match="filename"):
        load_cases(write_registry(tmp_path, text))


def test_load_cases_rejects_duplicate_case_id(tmp_path):
    case = registry()
    text = case + case.removeprefix("cases:\n").replace("example-", "copy-").replace(
        "case_id: copy-2026", "case_id: example-2026"
    )

    with pytest.raises(ValueError, match="example-2026"):
        load_cases(write_registry(tmp_path, text))


def test_every_source_has_licence_and_sha256():
    cases = load_cases()

    assert cases
    for case in cases.values():
        assert case.sources, case.case_id
        for source in case.sources:
            assert source.licence.strip(), source.doc_id
            assert source.attribution.strip(), source.doc_id
            assert re.fullmatch(r"[0-9a-f]{64}", source.sha256), source.doc_id


def test_verify_accepts_matching_file(tmp_path):
    case = one_case(tmp_path)
    (tmp_path / "example-2026").mkdir()
    for name in ("example-status.json", "example-postmortem.html"):
        (tmp_path / "example-2026" / name).write_bytes(b"abc")

    assert verify_local_files(case, tmp_path) == []


def test_verify_reports_hash_mismatch(tmp_path):
    case = one_case(tmp_path)
    (tmp_path / "example-2026").mkdir()
    (tmp_path / "example-2026" / "example-status.json").write_bytes(b"abd")
    (tmp_path / "example-2026" / "example-postmortem.html").write_bytes(b"abc")

    assert verify_local_files(case, tmp_path) == ["example-status"]


def test_verify_reports_missing_file(tmp_path):
    case = one_case(tmp_path)

    assert verify_local_files(case, tmp_path) == ["example-status", "example-postmortem"]


CHART_SOURCE = """\
      - doc_id: example-radar-traffic
        filename: radar-traffic.png
        url: https://radar.cloudflare.com/traffic?dateStart=2026-02-20&dateEnd=2026-02-20
        licence: CC BY 4.0
        attribution: Cloudflare Radar
        sha256: "{sha256}"
        retrieved_at: "2026-10-27T17:00:00Z"
        kind: chart
"""


def test_a_chart_source_with_a_display_licence_loads(tmp_path):
    case = load_cases(
        write_registry(tmp_path, registry() + CHART_SOURCE.replace("{sha256}", ABC_SHA256))
    )

    assert [s.kind for s in case["example-2026"].sources][-1] == "chart"


def test_chart_sources_need_a_display_licence(tmp_path):
    chart = CHART_SOURCE.replace("{sha256}", ABC_SHA256).replace(
        "licence: CC BY 4.0", "licence: Copyright Cloudflare; not redistributed"
    )

    with pytest.raises(ValueError, match="example-radar-traffic.*licence"):
        load_cases(write_registry(tmp_path, registry() + chart))


def test_verify_can_check_one_kind_of_source(tmp_path):
    case = one_case(tmp_path)
    (tmp_path / "example-2026").mkdir()
    (tmp_path / "example-2026" / "example-status.json").write_bytes(b"abc")

    assert verify_local_files(case, tmp_path, kinds=frozenset({"status-updates"})) == []
    assert verify_local_files(case, tmp_path) == ["example-postmortem"]
