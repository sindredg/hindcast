"""The web page: a stored investigation, rendered section by section, with its challenges.

Run with ``streamlit run src/hindcast/app.py``. The page lists the committed
development-case results and shows one at a time, the newest gpt-6-luna run
first. Under each finding it shows the challenges stored for that result.

With HINDCAST_CHALLENGE_LIVE=1, set only on a developer's machine, each
finding gets a question box that runs a challenge with the developer's
sign-in (hindcast.challenge) and stores it. The deployed page has no such
setting and no role to call a model, so it shows stored challenges only
(decision 0021).
"""

import json
import os
from pathlib import Path

import streamlit as st

from hindcast import telemetry
from hindcast.result import Citation, StoredResult, load_result

# Anchored to the repository root, because Streamlit runs the script from its
# own directory; in the image the root is /app.
ROOT = Path(__file__).resolve().parents[2]
RESULT_DIR = ROOT / "eval/investigations/cloudflare-2026-02-20"
DEFAULT_DEPLOYMENT = "gpt-6-luna"
# Test seam: points the page at one result file instead of the list.
RESULT_FILE_VAR = "HINDCAST_RESULT_FILE"
CHALLENGE_LIVE_VAR = "HINDCAST_CHALLENGE_LIVE"


def results(directory: Path) -> list[Path]:
    """The result files, newest first: their names start with the UTC run time."""
    return sorted(directory.glob("*.json"), reverse=True)


def default_result(directory: Path) -> Path:
    files = results(directory)
    for path in files:
        if json.loads(path.read_text("utf-8"))["model"]["deployment"] == DEFAULT_DEPLOYMENT:
            return path
    return files[0]


def challenges(result_path: Path, finding_id: str) -> list[dict]:
    """The stored challenges of one finding of this result, oldest first."""
    found = []
    for path in sorted((result_path.parent / "challenges").glob(f"*-{finding_id}.json")):
        stored = json.loads(path.read_text("utf-8"))
        # The folder holds the challenges of every result of the case.
        if stored.get("result_file") == result_path.name and stored["finding_id"] == finding_id:
            found.append(stored)
    return found


def _cites(citations: tuple[Citation, ...]) -> str:
    # Citations render as their IDs; resolving them to the source text comes
    # with the interface slice.
    return " ".join(f"`{c.source}:{c.ref}`" for c in citations) or "no citation"


def _rests_on(ids: tuple[str, ...]) -> str:
    return ", ".join(f"`{i}`" for i in ids) or "nothing"


def _challenge(stored: dict) -> None:
    st.markdown(f"**Challenge:** {stored['question']}")
    answer = stored.get("challenge")
    if answer is None:
        st.markdown(f"No answer: {stored['status']} ({stored.get('reason')})")
        return
    st.markdown(f"**{answer['verdict']}**: {answer['answer']}")
    if answer.get("revised_claim"):
        st.markdown(f"Revised claim: {answer['revised_claim']}")
    st.markdown(
        " ".join(f"`{c['source']}:{c['ref']}`" for c in answer["citations"]) or "no citation"
    )
    checks = stored.get("checks", {})
    rejected, pii = checks.get("rejected_citations", []), checks.get("pii", [])
    if rejected or pii:
        st.markdown(f"Rejected citations: {len(rejected)}. PII hits: {len(pii)}.")


def _live_challenge(path: Path, finding_id: str) -> None:
    question = st.text_area("Challenge this finding", key=f"question-{finding_id}")
    if st.button("Run challenge", key=f"challenge-{finding_id}") and question.strip():
        # Imported here: the deployed page never runs a challenge.
        from hindcast import challenge

        with st.spinner("Running the challenge"):
            result, written, cost = challenge.challenge_and_store(path, finding_id, question)
        if result.challenge is None:
            st.warning(f"No answer: {result.status} ({result.reason})")
            return
        st.markdown(f"**{result.challenge.verdict}**: {result.challenge.answer}")
        if result.challenge.revised_claim:
            st.markdown(f"Revised claim: {result.challenge.revised_claim}")
        st.markdown(_cites(result.challenge.citations))
        st.caption(f"Stored in {written.name}; cost {cost.get('currency')} {cost.get('total')}")


def _render(result: StoredResult, path: Path, live: bool) -> None:
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
                for stored in challenges(path, finding.id):
                    _challenge(stored)
                if live and result.status == "complete" and "screen_calls" in result.usage:
                    _live_challenge(path, finding.id)

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
    withheld = [ref for call in result.tool_calls for ref in call.get("withheld", [])]
    st.markdown(f"Withheld items: {len(withheld)}. " + " ".join(f"`{r}`" for r in withheld))
    pii = result.checks.get("pii", [])
    st.markdown(
        f"PII hits: {len(pii)}. " + " ".join(f"`{hit['path']}` ({hit['category']})" for hit in pii)
    )

    st.header("Usage")
    if result.cost is not None:
        st.markdown(
            f"Cost: {result.cost.get('currency')} {result.cost['total']}"
            f" (price table v{result.cost.get('table_version')})"
            if "total" in result.cost
            else f"Cost not priced: {result.cost.get('error')}"
        )
    st.json(result.usage)
    st.markdown("Provenance")
    st.json(result.provenance)


def main() -> None:
    st.set_page_config(page_title="Hindcast", layout="wide")
    telemetry.configure()
    override = os.environ.get(RESULT_FILE_VAR, "")
    if override:
        path = Path(override)
    else:
        files = results(RESULT_DIR)
        default = default_result(RESULT_DIR)
        path = st.selectbox(
            "Result", files, index=files.index(default), format_func=lambda p: p.name
        )
    live = os.environ.get(CHALLENGE_LIVE_VAR) == "1"
    result = load_result(path)
    with telemetry.span("page_view", case_id=result.case_id, result_file=path.name):
        _render(result, path, live)


if __name__ == "__main__":
    main()
