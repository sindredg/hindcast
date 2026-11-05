"""The web page: investigations, rendered section by section, with their challenges.

Run with ``streamlit run src/hindcast/app.py``. The page lists the committed
development-case results and the page's own runs, and shows one at a time,
the newest gpt-6-luna run first. Under each finding it shows the challenges
stored for that result.

With HINDCAST_LIVE=1 the page runs investigations of the development case
and its injection copies, and each finding of a screened result gets a
question box that runs a challenge (decision 0028). Scored and sealed cases
are refused. On a developer's machine the calls use the developer's sign-in
and the local build/; the deployed app also sets HINDCAST_BLOB_RUNTIME=1, so
the page first downloads its runtime files from Blob Storage and stores every
run and challenge there, with the app's managed identity.
"""

import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

from hindcast import runtime, storage, telemetry
from hindcast.cases import Case
from hindcast.result import Citation, StoredResult, load_result

# Anchored to the repository root, because Streamlit runs the script from its
# own directory; in the image the root is /app.
ROOT = Path(__file__).resolve().parents[2]
RESULT_DIR = ROOT / "eval/investigations/cloudflare-2026-02-20"
DEFAULT_DEPLOYMENT = "gpt-6-luna"
# Test seam: points the page at one result file instead of the list.
RESULT_FILE_VAR = "HINDCAST_RESULT_FILE"
LIVE_VAR = "HINDCAST_LIVE"
BLOB_RUNTIME_VAR = "HINDCAST_BLOB_RUNTIME"
# Test seam: where build/ and the stored runs live. In the image it is /app,
# the working directory the investigator's relative paths resolve against.
RUN_ROOT_VAR = "HINDCAST_RUN_ROOT"
# The only roles the page investigates: scored runs are evaluation runs, and
# a sealed case is never run before its reveal.
LIVE_ROLES = frozenset({"development", "injection"})
# Shared by every session of the process (hindcast.runtime explains why).
RUN_LOCK = runtime.RUN_LOCK


class RunInProgress(RuntimeError):
    """Another investigation is running in this process."""


class StoreFailed(RuntimeError):
    """The run completed and was written under build/, but storing it in Blob failed."""

    def __init__(self, path: Path, error: Exception) -> None:
        super().__init__(f"{path.name} was written but not stored: {error}")
        self.path = path


def run_root() -> Path:
    return Path(os.environ.get(RUN_ROOT_VAR) or ROOT)


def live_cases(cases: Mapping[str, Case]) -> list[str]:
    """The cases the page may investigate, sorted."""
    return sorted(c for c, case in cases.items() if case.role in LIVE_ROLES)


def start_run(case: Case, *, root: Path, client: storage.Blobs | None) -> Path:
    """Investigate one case, write the result under root, and store it when a client is given.

    Refused before any cloud call when another run holds the lock or the
    case is not a development or injection case.
    """
    if not RUN_LOCK.acquire(blocking=False):
        raise RunInProgress("an investigation is already running; wait for it to finish")
    try:
        if case.role not in LIVE_ROLES:
            raise PermissionError(f"{case.case_id} is a {case.role} case: the page does not run it")
        from hindcast import investigate

        investigate.check_case_allowed(case, investigate.RUBRIC_LOCK)
        setup = investigate.prepare(case)
        result = investigate.run_investigation(
            setup.turn, setup.tools, case_id=case.case_id, pii=setup.pii
        )
        path = investigate.write_result(
            result,
            case_id=case.case_id,
            agent=setup.agent,
            model=setup.model,
            provenance=setup.provenance,
            out_dir=root / "build/investigations",
            now=datetime.now(UTC),
            cost=setup.cost(result.usage),
        )
        if client is not None:
            try:
                runtime.store_run(client, root, path)
            except Exception as error:  # noqa: BLE001
                # The paid run is on disk until the replica stops; the page
                # shows it and says so, so it can be stored by hand.
                raise StoreFailed(path, error) from error
        return path
    finally:
        RUN_LOCK.release()


@st.cache_resource
def _runtime_ready(root: str) -> bool:
    """Download the runtime files and the stored runs once per process.

    An exception is not cached, so a failed download is tried again on the
    next render; materialize leaves nothing behind when it fails.
    """
    runtime.materialize(storage.container(runtime.RUNTIME), Path(root))
    runtime.fetch_runs(storage.container(runtime.RUNS), Path(root))
    return True


def _runs_client() -> storage.Blobs | None:
    if os.environ.get(BLOB_RUNTIME_VAR) != "1":
        return None
    return storage.container(runtime.RUNS)


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
        # Imported here: a page without the live flag never runs a challenge.
        from hindcast import challenge

        with st.spinner("Running the challenge"):
            result, written, cost = challenge.challenge_and_store(path, finding_id, question)
        client = _runs_client()
        if client is not None:
            runtime.store_run(client, run_root(), written)
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


def _investigate_panel(cases: Mapping[str, Case]) -> None:
    with st.sidebar:
        st.header("Run an investigation")
        case_id = st.selectbox("Case", live_cases(cases), key="case")
        if st.button("Investigate", key="investigate") and case_id:
            try:
                with st.status(f"Investigating {case_id}", expanded=False):
                    path = start_run(cases[case_id], root=run_root(), client=_runs_client())
            except RunInProgress as error:
                st.warning(str(error))
                return
            except StoreFailed as error:
                # No rerun: the message stays, and the selectbox below picks
                # the written result.
                st.error(str(error))
                st.session_state["picked"] = str(error.path)
                return
            except Exception as error:  # noqa: BLE001
                # Shown, not raised: a traceback would print the endpoints.
                st.error(f"The investigation failed: {error}")
                return
            st.session_state["picked"] = str(path)
            st.rerun()


def _result_files(cases: Mapping[str, Case]) -> list[Path]:
    """Committed development results, then the page's own runs, newest first in each."""
    own = [
        p
        for case_id in live_cases(cases)
        for p in results(run_root() / "build/investigations" / case_id)
    ]
    return results(RESULT_DIR) + sorted(own, key=lambda p: p.name, reverse=True)


def main() -> None:
    st.set_page_config(page_title="Hindcast", layout="wide")
    telemetry.configure()
    live = os.environ.get(LIVE_VAR) == "1"
    cases: Mapping[str, Case] = {}
    if live:
        from hindcast.cases import load_cases

        cases = load_cases()
        ready = True
        if os.environ.get(BLOB_RUNTIME_VAR) == "1":
            try:
                ready = _runtime_ready(str(run_root()))
            except Exception as error:  # noqa: BLE001
                # Shown, not raised: the stored results still render, and no
                # run starts on a partial or unchecked build/.
                st.error(f"The runtime files are not ready: {error}")
                ready = False
        if ready:
            _investigate_panel(cases)
        # Without the runtime files a challenge cannot run either.
        live = ready
    override = os.environ.get(RESULT_FILE_VAR, "")
    if override:
        path = Path(override)
    else:
        files = _result_files(cases)
        picked = Path(st.session_state.get("picked", "")) if "picked" in st.session_state else None
        default = picked if picked in files else default_result(RESULT_DIR)
        path = st.selectbox(
            "Result", files, index=files.index(default), format_func=lambda p: p.name
        )
    result = load_result(path)
    with telemetry.span("page_view", case_id=result.case_id, result_file=path.name):
        _render(result, path, live)


if __name__ == "__main__":
    main()
