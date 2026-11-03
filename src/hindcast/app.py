"""The web page: one stored investigation, rendered section by section.

Run with ``streamlit run src/hindcast/app.py``. The page reads the committed
development-case result; the interface slice replaces the file with a live
run from the investigator.
"""

import os
from pathlib import Path

import streamlit as st

from hindcast import telemetry
from hindcast.result import Citation, StoredResult, load_result

# The one result the page shows until it runs investigations itself. Anchored
# to the repository root, because Streamlit runs the script from its own
# directory; in the image the root is /app.
ROOT = Path(__file__).resolve().parents[2]
RESULT_FILE = ROOT / "eval/investigations/cloudflare-2026-02-20/20261102T181721Z-v3.json"
# Test seam: points the page at another result file.
RESULT_FILE_VAR = "HINDCAST_RESULT_FILE"


def _cites(citations: tuple[Citation, ...]) -> str:
    # Citations render as their IDs; resolving them to the source text comes
    # with the interface slice.
    return " ".join(f"`{c.source}:{c.ref}`" for c in citations) or "no citation"


def _rests_on(ids: tuple[str, ...]) -> str:
    return ", ".join(f"`{i}`" for i in ids) or "nothing"


def _render(result: StoredResult) -> None:
    st.title("Hindcast")
    st.caption(
        f"Case `{result.case_id}` · agent {result.agent.get('name')} v{result.agent.get('version')}"
        f" · model {result.model.get('name')} {result.model.get('version')}"
    )
    if result.status != "complete":
        st.warning(f"Incomplete run: {result.incomplete_reason}")

    investigation = result.investigation
    if investigation is not None:
        st.header("Attack assessment")
        st.markdown(f"**{investigation.attack.verdict}**")
        st.markdown(investigation.attack.reasoning)
        st.markdown(_cites(investigation.attack.citations))

        st.header("Root cause")
        st.markdown(investigation.root_cause.claim)
        st.markdown(f"Rests on {_rests_on(investigation.root_cause.rests_on)}")
        st.markdown(_cites(investigation.root_cause.citations))

        st.header("Timeline")
        st.table(
            [
                {
                    "time": t.time,
                    "kind": t.time_kind,
                    "event": t.event,
                    "citations": " ".join(f"{c.source}:{c.ref}" for c in t.citations),
                }
                for t in investigation.timeline
            ]
        )

        st.header("Findings")
        for finding in investigation.findings:
            with st.expander(f"{finding.id} ({finding.kind})"):
                st.markdown(finding.claim)
                st.markdown(f"Rests on {_rests_on(finding.rests_on)}")
                st.markdown(_cites(finding.citations))

        st.header("Contributing factors")
        for factor in investigation.contributing_factors:
            st.markdown(
                f"- {factor.claim} (rests on {_rests_on(factor.rests_on)};"
                f" {_cites(factor.citations)})"
            )

        st.header("Open questions")
        for question in investigation.open_questions:
            st.markdown(f"- {question.question} *{question.why_open}*")

    st.header("Checks")
    rejected = result.checks.get("rejected_citations", [])
    unsupported = result.checks.get("unsupported", [])
    st.markdown(f"Rejected citations: {len(rejected)}. Unsupported items: {len(unsupported)}.")
    if rejected:
        st.table(rejected)
    if unsupported:
        st.markdown("\n".join(f"- `{item}`" for item in unsupported))

    st.header("Usage")
    st.json(result.usage)
    st.markdown("Provenance")
    st.json(result.provenance)


def main() -> None:
    st.set_page_config(page_title="Hindcast", layout="wide")
    telemetry.configure()
    path = Path(os.environ.get(RESULT_FILE_VAR, "") or RESULT_FILE)
    result = load_result(path)
    with telemetry.span("page_view", case_id=result.case_id, result_file=str(path)):
        _render(result)


if __name__ == "__main__":
    main()
