"""A citation resolves to the item the run read, and to nothing else."""

import json

from hindcast import cited, investigate

CASE = "cloudflare-2026-02-20"
COPY = "cloudflare-2026-02-20-inject-chart"


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _evidence(root, case_id, *, updates=(), charts=()):
    _write(
        root / cited.EVIDENCE_DIR / f"{case_id}.json",
        {
            "case_id": case_id,
            "provider": "Cloudflare",
            "title": "t",
            "started_at": "2026-02-20T18:45:16Z",
            "updates": list(updates),
            "dropped": [],
            "charts": list(charts),
        },
    )


def _chart(case_id, n, *, display):
    return {
        "chart_id": f"{case_id}/chart{n}",
        "filename": f"radar-{n}.png",
        "description": f"DESCRIPTION {n}",
        "alt_text": f"ALT {n}",
        "display": display,
    }


def test_the_evidence_folder_is_the_investigators():
    assert cited.EVIDENCE_DIR == investigate.EVIDENCE_DIR


def test_an_update_resolves_with_its_time_status_and_text(tmp_path):
    update = {"update_id": f"{CASE}/u2", "time": "T2", "status": "identified", "text": "TEXT"}
    _evidence(tmp_path, CASE, updates=[update])

    item = cited.resolve(tmp_path, CASE, "case", f"{CASE}/u2")

    assert item == cited.Cited("update", f"{CASE}/u2", "Update u2 · identified", "T2", "TEXT")


def test_the_resolved_update_says_its_text_is_withheld(tmp_path):
    update = {"update_id": f"{CASE}/u9", "time": "T9", "status": "resolved", "text": None}
    _evidence(tmp_path, CASE, updates=[update])

    item = cited.resolve(tmp_path, CASE, "case", f"{CASE}/u9")

    assert item is not None and "withheld" in item.text


def test_a_chart_image_is_offered_only_when_its_licence_allows_it(tmp_path):
    _evidence(
        tmp_path, CASE, charts=[_chart(CASE, 1, display=True), _chart(CASE, 2, display=False)]
    )
    for n in (1, 2):
        image = tmp_path / cited.CHARTS_DIR / CASE / f"radar-{n}.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"png")

    shown = cited.resolve(tmp_path, CASE, "case", f"{CASE}/chart1")
    hidden = cited.resolve(tmp_path, CASE, "case", f"{CASE}/chart2")

    assert shown is not None and shown.image == tmp_path / cited.CHARTS_DIR / CASE / "radar-1.png"
    assert shown.text == "DESCRIPTION 1" and "ALT 1" in shown.heading
    assert hidden is not None and hidden.image is None


def test_an_injection_copy_shows_the_development_case_chart_files(tmp_path):
    _evidence(tmp_path, COPY, charts=[_chart(COPY, 1, display=True)])
    image = tmp_path / cited.CHARTS_DIR / CASE / "radar-1.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"png")

    item = cited.resolve(tmp_path, COPY, "case", f"{COPY}/chart1")

    assert item is not None and item.image == image


def test_a_missing_image_file_is_no_image(tmp_path):
    _evidence(tmp_path, CASE, charts=[_chart(CASE, 1, display=True)])

    item = cited.resolve(tmp_path, CASE, "case", f"{CASE}/chart1")

    assert item is not None and item.image is None


def test_another_cases_ref_never_reads_that_case(tmp_path):
    other = "github-2026-10-21"
    _evidence(
        tmp_path,
        other,
        updates=[{"update_id": f"{other}/u1", "time": "", "status": "", "text": "X"}],
    )
    _evidence(tmp_path, CASE)

    assert cited.resolve(tmp_path, CASE, "case", f"{other}/u1") is None


def test_a_malformed_case_id_is_not_a_path(tmp_path):
    _evidence(
        tmp_path, CASE, updates=[{"update_id": f"{CASE}/u1", "time": "", "status": "", "text": "X"}]
    )

    assert cited.resolve(tmp_path / "build", f"../{CASE}", "case", f"../{CASE}/u1") is None


def test_no_evidence_file_resolves_nothing(tmp_path):
    assert cited.resolve(tmp_path, CASE, "case", f"{CASE}/u1") is None
    assert cited.resolve(tmp_path, CASE, "library", "lib/cloudflare-2019-07-02/s1") is None


def test_a_broken_evidence_file_resolves_nothing(tmp_path):
    path = tmp_path / cited.EVIDENCE_DIR / f"{CASE}.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")

    assert cited.resolve(tmp_path, CASE, "case", f"{CASE}/u1") is None


def _library(folder, doc_id):
    _write(
        folder / f"{doc_id}.json",
        {
            "doc_id": doc_id,
            "published_at": "2019-07-12",
            "sections": [{"section_id": f"lib/{doc_id}/s1", "heading": "H", "markdown": "BODY"}],
            "figures": [{"figure_id": f"lib/{doc_id}/fig1", "description": "FIG"}],
            "dropped": [],
        },
    )


def test_a_library_section_and_figure_resolve(tmp_path):
    from hindcast.index import EXTRACTS_DIR

    _library(tmp_path / EXTRACTS_DIR, "cloudflare-2019-07-02")

    section = cited.resolve(tmp_path, CASE, "library", "lib/cloudflare-2019-07-02/s1")
    figure = cited.resolve(tmp_path, CASE, "library", "lib/cloudflare-2019-07-02/fig1")

    assert section == cited.Cited(
        "section", "lib/cloudflare-2019-07-02/s1", "H", "2019-07-12", "BODY"
    )
    assert figure is not None and figure.kind == "figure" and figure.text == "FIG"


def test_a_planted_library_page_resolves(tmp_path):
    from hindcast import injection

    _library(tmp_path / injection.EXTRACTS_DIR, "injection-planted-library")

    item = cited.resolve(tmp_path, CASE, "library", "lib/injection-planted-library/s1")

    assert item is not None and item.text == "BODY"


def test_a_library_ref_outside_the_library_form_is_refused(tmp_path):
    from hindcast.index import EXTRACTS_DIR

    _library(tmp_path / EXTRACTS_DIR, "cloudflare-2019-07-02")

    for ref in ("lib/../cloudflare-2019-07-02/s1", "lib/Cloudflare-2019-07-02/s1", "lib//s1"):
        assert cited.resolve(tmp_path, CASE, "library", ref) is None
    # A library ref cited as a case ref, and an unknown source, resolve to nothing.
    assert cited.resolve(tmp_path, CASE, "case", "lib/cloudflare-2019-07-02/s1") is None
    assert cited.resolve(tmp_path, CASE, "", "lib/cloudflare-2019-07-02/s1") is None


def test_short_names_drop_the_case_prefix():
    assert cited.short(f"{CASE}/u7", CASE) == "u7"
    assert cited.short("lib/cloudflare-2019-07-02/s3", CASE) == "cloudflare-2019-07-02 s3"
    assert cited.short("other/u1", CASE) == "other/u1"
