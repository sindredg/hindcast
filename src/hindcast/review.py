"""The review page: a person decides what the judges proposed, one item at a time.

    PYTHONPATH=src uv run --frozen streamlit run src/hindcast/review.py

Run from the repository root, on a local machine only; it is never deployed.
It reads the scored runs, their judgments, the frozen keys, the local
evidence, and the library extracts, and writes the decisions to
reviews/<run_id>.json under the evaluation folder (hindcast.evaluation.review).

Runs appear under a blind ID in a fixed shuffled order, without their arm or
model. Each screen shows one item: a key item with the run items the judge
matched to it, or one run item with its support verdict, next to the text
every cited ref points to. The judge's proposal is marked on its button.
The page resumes at the first item without a decision.

The second mode reviews the prior-knowledge answers the same way
(hindcast.evaluation.judge_prior): the answer, the key item, and the
judge's proposal, under a blind ID that hides the model.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st

from hindcast import excerpts
from hindcast.evaluation import judge
from hindcast.evaluation.batch import FILLED, load_attempts, verified_run
from hindcast.evaluation.review import (
    ReviewItem,
    blind_id,
    choices,
    load_review,
    pending,
    prior_queue,
    record_decision,
    review_queue,
    run_order,
    undo_last,
)
from hindcast.evidence import CaseEvidence
from hindcast.keys import AnswerKey
from hindcast.result import LIBRARY_PREFIX, Citation

# Test seam and a way to review another evaluation folder.
ROOT_VAR = "HINDCAST_REVIEW_ROOT"
DEFAULT_ROOT = Path("eval/reconstruction/showcase-v1")
PRIOR_ROOT_VAR = "HINDCAST_REVIEW_PRIOR_ROOT"
DEFAULT_PRIOR_ROOT = Path("eval/prior-knowledge/v1")
MODES = ("Reconstructions", "Prior knowledge")
_MARKDOWN = str.maketrans({c: f"\\{c}" for c in "\\`*_{}[]<>()#+-.!|~$"})


@dataclass(frozen=True)
class Run:
    run_id: str
    blind: str
    record: dict
    judgment_sha256: str
    document: dict
    key: AnswerKey
    evidence: CaseEvidence
    items: dict[str, dict]


@dataclass(frozen=True)
class Answer:
    # <answer file stem>/<case_id>
    record_id: str
    blind: str
    record: dict
    judgment_sha256: str
    question: str
    answer: str
    key: AnswerKey


def _plain(text: str) -> str:
    """Text shown as written: Markdown characters escaped, line breaks kept."""
    return text.translate(_MARKDOWN).replace("\n", "  \n")


def load_runs(root: Path) -> tuple[list[Run], int]:
    """The judged runs in blind order, and how many filled runs have no judgment yet."""
    runs: dict[str, Run] = {}
    not_judged = 0
    for entry in load_attempts(root / "attempts.json"):
        if entry["status"] not in FILLED:
            continue
        path = judge.judgment_path(root / "judgments", entry["run_id"])
        if not path.is_file():
            not_judged += 1
            continue
        data = path.read_bytes()
        record = json.loads(data)
        if record["error"] is not None:
            not_judged += 1
            continue
        document = verified_run(entry, root / "runs")
        key, evidence = judge.load_case(entry["case_id"])
        items = {i["where"]: i for i in judge.run_items(document["investigation"])}
        runs[entry["run_id"]] = Run(
            run_id=entry["run_id"],
            blind=blind_id(entry["run_id"]),
            record=record,
            judgment_sha256=judge._sha256(data),
            document=document,
            key=key,
            evidence=evidence,
            items=items,
        )
    return [runs[r] for r in run_order(runs)], not_judged


def load_answers(root: Path) -> tuple[list[Answer], int]:
    """The judged prior-knowledge answers in blind order, and how many have no judgment."""
    answers: dict[str, Answer] = {}
    not_judged = 0
    for path in sorted((root / "judgments").glob("*/*.json")):
        data = path.read_bytes()
        record = json.loads(data)
        if record["error"] is not None:
            not_judged += 1
            continue
        collection = json.loads(Path(record["answers"]).read_text(encoding="utf-8"))
        [entry] = [e for e in collection["entries"] if e["case_id"] == record["case_id"]]
        record_id = f"{path.parent.name}/{path.stem}"
        answers[record_id] = Answer(
            record_id=record_id,
            blind=blind_id(f"prior/{record_id}"),
            record=record,
            judgment_sha256=judge._sha256(data),
            question=entry["question"],
            answer=entry["answer"],
            key=judge.load_case(record["case_id"])[0],
        )
    order = sorted(answers, key=lambda r: answers[r].blind)
    return [answers[r] for r in order], not_judged


def _review_path(root: Path, record_id: str) -> Path:
    return root / "reviews" / f"{record_id}.json"


def _cited(run: Run, refs: list[str], library: dict[str, dict]) -> None:
    for ref in refs:
        source = "library" if ref.startswith(LIBRARY_PREFIX) else "case"
        excerpt = excerpts.resolve(Citation(source, ref), run.evidence, library)
        with st.container(border=True):
            if excerpt is None:
                st.error(f"{ref}: no text found")
                continue
            st.caption(f"{ref} · {excerpt.title}")
            st.markdown(_plain(excerpt.text))


def _verdict(run: Run, where: str) -> str:
    verdict = run.record["judgment"]["run_items"][where]
    word = "supported" if verdict["supported"] else "unsupported"
    fixed = " (fixed by the code's check)" if where in run.record["code_unsupported"] else ""
    return f"Judge: {word}{fixed}. {verdict['reason']}"


def _run_item(run: Run, where: str, library: dict[str, dict], *, depth: int = 0) -> None:
    item = run.items[where]
    st.markdown(f"**{where}** ({item['kind']}): {_plain(item['text'])}")
    st.caption(_plain(_verdict(run, where)))
    if item["citations"]:
        _cited(run, item["citations"], library)
    by_id = {i["id"]: w for w, i in run.items.items() if "id" in i}
    for finding_id in item["rests_on"]:
        if finding_id not in by_id:
            continue
        if depth == 0:
            with st.expander(f"Rests on {finding_id} ({by_id[finding_id]})"):
                _run_item(run, by_id[finding_id], library, depth=1)
        else:
            st.caption(f"Rests on {finding_id} ({by_id[finding_id]})")


def _match(run: Run, item: ReviewItem, library: dict[str, dict]) -> None:
    key_item = {k["id"]: k for k in judge.key_items(run.key)}[item.item]
    verdict = run.record["judgment"]["key_items"][item.item]
    st.subheader(f"Key item {item.item}")
    if "time" in key_item:
        st.markdown(f"**{key_item['time']}** (postmortem: {_plain(key_item['time_as_written'])})")
    st.markdown(_plain(key_item["text"]))
    if key_item["quote"]:
        st.caption("Postmortem: " + _plain(key_item["quote"]))
    st.markdown(f"**Judge proposes: {verdict['outcome']}.** {_plain(verdict['reason'])}")
    if not verdict["run_items"]:
        st.info("The judge lists no run item. The whole run is below.")
    for where in verdict["run_items"]:
        st.divider()
        _run_item(run, where, library)


def _buttons(record_id: str, judgment_sha256: str, item: ReviewItem, path: Path) -> None:
    options = choices(item)
    columns = st.columns(len(options))
    for column, option in zip(columns, options, strict=True):
        label = (
            ("Supported" if option else "Unsupported") if item.kind == "support" else str(option)
        )
        if option == item.proposal:
            label = f"{label} (judge)"
        widget_key = f"{record_id}|{item.kind}|{item.item}|{option}"
        if column.button(label, key=widget_key, width="stretch"):
            record_decision(path, record_id, judgment_sha256, item, option)
            st.rerun()


def _whole_run(run: Run) -> None:
    with st.expander("The whole run"):
        for where, item in run.items.items():
            st.markdown(f"**{where}** ({item['kind']}): {_plain(item['text'])}")
        questions = run.document["investigation"]["open_questions"]
        if questions:
            st.markdown("**Open questions**")
            for q in questions:
                st.markdown(f"- {_plain(q['question'])} ({_plain(q['why_open'])})")


def _undo_latest(paths: list[Path]) -> None:
    latest: tuple[str, Path] | None = None
    for path in paths:
        if not path.is_file():
            continue
        decisions = json.loads(path.read_text(encoding="utf-8"))["decisions"]
        if decisions and (latest is None or decisions[-1]["decided_at"] >= latest[0]):
            latest = (decisions[-1]["decided_at"], path)
    if latest is not None:
        undo_last(latest[1])


def _progress(
    queues: list[tuple[Any, Path, list[ReviewItem], list[ReviewItem]]], note: str
) -> None:
    total = sum(len(q) for _, _, q, _ in queues)
    left = sum(len(p) for _, _, _, p in queues)
    with st.sidebar:
        st.metric("Decided", f"{total - left} of {total}")
        st.caption(note)
        if st.button("Undo the last decision"):
            _undo_latest([path for _, path, _, _ in queues])
            st.rerun()


def _reconstructions(root: Path) -> None:
    runs, not_judged = load_runs(root)
    library: dict[str, Any] = excerpts.load_library_items() if runs else {}
    queues: list[tuple[Any, Path, list[ReviewItem], list[ReviewItem]]] = []
    for run in runs:
        path = _review_path(root, run.run_id)
        queue = review_queue(run.record)
        review = load_review(path, run.run_id, run.judgment_sha256)
        queues.append((run, path, queue, pending(queue, review)))
    _progress(queues, f"{len(runs)} judged runs; {not_judged} without a judgment")
    current = next(((r, p, q, todo) for r, p, q, todo in queues if todo), None)
    if current is None:
        st.success("Every item is decided.")
        return
    run, path, queue, todo = current
    item = todo[0]
    st.title(f"Run {run.blind}")
    st.caption(
        f"{_plain(run.evidence.title)} · item {len(queue) - len(todo) + 1} of {len(queue)}"
        f" in this run · {'sampled' if item.sampled else 'required'}"
    )
    if item.kind == "match":
        _match(run, item, library)
    else:
        st.subheader(f"Support of {item.item}")
        _run_item(run, item.item, library)
    st.divider()
    _buttons(run.run_id, run.judgment_sha256, item, path)
    _whole_run(run)


def _prior(root: Path) -> None:
    answers, not_judged = load_answers(root)
    queues: list[tuple[Any, Path, list[ReviewItem], list[ReviewItem]]] = []
    for answer in answers:
        path = _review_path(root, answer.record_id)
        queue = prior_queue(answer.record, answer.record_id)
        review = load_review(path, answer.record_id, answer.judgment_sha256)
        queues.append((answer, path, queue, pending(queue, review)))
    _progress(queues, f"{len(answers)} judged answers; {not_judged} without a judgment")
    current = next(((a, p, q, todo) for a, p, q, todo in queues if todo), None)
    if current is None:
        st.success("Every item is decided.")
        return
    answer, path, _, todo = current
    item = todo[0]
    st.title(f"Answer {answer.blind}")
    st.caption(f"Before any evidence · {'sampled' if item.sampled else 'required'}")
    st.markdown(f"**Question:** {_plain(answer.question)}")
    with st.container(border=True):
        st.markdown(_plain(answer.answer))
    key = answer.key
    text, quote = (
        (key.attack, key.attack_quote)
        if item.item == "attack"
        else (key.root_cause.text, key.root_cause.source_quote)
    )
    st.subheader(f"Key item {item.item}")
    st.markdown(_plain(text))
    if quote:
        st.caption("Postmortem: " + _plain(quote))
    verdict = answer.record["judgment"][item.item]
    st.markdown(f"**Judge proposes: {verdict['outcome']}.** {_plain(verdict['reason'])}")
    st.divider()
    _buttons(answer.record_id, answer.judgment_sha256, item, path)


def main() -> None:
    st.set_page_config(page_title="Hindcast review", layout="wide")
    with st.sidebar:
        mode = st.radio("Review", MODES)
    if mode == MODES[0]:
        _reconstructions(Path(os.environ.get(ROOT_VAR) or DEFAULT_ROOT))
    else:
        _prior(Path(os.environ.get(PRIOR_ROOT_VAR) or DEFAULT_PRIOR_ROOT))


if __name__ == "__main__":
    main()
