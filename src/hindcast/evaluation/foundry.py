"""Foundry cloud evaluation of the scored runs (decision 0006).

    PYTHONPATH=src uv run --frozen python -m hindcast.evaluation.foundry build
    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.evaluation.foundry submit
    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.evaluation.foundry results

`build` writes two datasets under build/foundry/, ignored by Git because they
hold status-page and library text: one row per scored run for groundedness
and relevance, and one row per agent-arm run for tool call accuracy. A result
file keeps the refs its tools returned, not the text, so each run's tool
outputs are rebuilt by replaying its recorded calls through CaseTools on the
same evidence, with the screen's recorded flags and the indexed chunks of the
recorded library refs. A replay that does not reproduce the recorded refs and
withheld items is refused.

`submit` uploads both datasets, creates one evaluation per dataset with the
generally available evaluators on the judge deployment, starts a run each,
and records the IDs. `results` waits for the runs and writes, per arm and
evaluator, the rows passed, failed, and errored (#7) and the mean score.
Nothing here prints run text or an evaluator's reason.
"""

import argparse
import hashlib
import json
import time
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from hindcast.arms import ARMS, arm_definition
from hindcast.evaluation.batch import ATTEMPTS, FILLED, RUNS_DIR, load_attempts, verified_run
from hindcast.evidence import evidence_json
from hindcast.investigate import START
from hindcast.search import LibraryHit
from hindcast.tools import CaseTools

OUT_DIR = Path("build/foundry")
RECORD_DIR = Path("eval/reconstruction/showcase-v1/foundry")
EVIDENCE_DIR = Path("build/evidence")
# Chosen on 2026-11-04 over a model that is not an arm. It judges its own
# comparison arm, which the report states next to the scores.
JUDGE_DEPLOYMENT = "gpt-6.1-sol"
DATASET_VERSION = "1"
# Repeat 1 of each arm and case, a third of the scored runs: the judge's
# tokens for all of them did not fit what was left to spend (2026-11-04).
REPEATS = (1,)
# The task every agent arm was given; the single-search arm got the tool
# outputs as its input instead, and they are its context here too.
QUERY = START["content"]


@dataclass(frozen=True)
class Dataset:
    name: str
    criteria: tuple[str, ...]
    agent_arms_only: bool


# Generally available evaluators only (decision 0006). Tool call accuracy
# needs the model's own tool calls, which the single-search arm does not make.
DATASETS = (
    Dataset("hindcast-showcase-v1-quality", ("groundedness", "relevance"), False),
    Dataset("hindcast-showcase-v1-tools", ("tool_call_accuracy",), True),
)
MAPPINGS = {
    "groundedness": {
        "query": "{{item.query}}",
        "response": "{{item.response}}",
        "context": "{{item.context}}",
    },
    "relevance": {"query": "{{item.query}}", "response": "{{item.response}}"},
    "tool_call_accuracy": {
        "query": "{{item.query}}",
        "response": "{{item.response}}",
        "tool_definitions": "{{item.tool_definitions}}",
    },
}
STRING_OR_MESSAGES = {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "object"}}]}


class ReplayMismatch(ValueError):
    """A replayed tool call returned other refs or withheld other items than the run did."""


def criteria_for(dataset: Dataset, deployment: str = JUDGE_DEPLOYMENT) -> list[dict]:
    return [
        {
            "type": "azure_ai_evaluator",
            "name": name,
            "evaluator_name": f"builtin.{name}",
            "initialization_parameters": {"deployment_name": deployment},
            "data_mapping": MAPPINGS[name],
        }
        for name in dataset.criteria
    ]


def item_schema(dataset: Dataset) -> dict:
    fields: dict[str, Any] = {"run_id": {"type": "string"}, "arm": {"type": "string"}}
    fields |= {"case_id": {"type": "string"}, "query": STRING_OR_MESSAGES}
    fields["response"] = STRING_OR_MESSAGES
    if dataset.agent_arms_only:
        fields["tool_definitions"] = {"type": "array", "items": {"type": "object"}}
    else:
        fields["context"] = {"type": "string"}
    return {"type": "object", "properties": fields, "required": sorted(fields)}


def library_hits(chunks: Iterable[Any]) -> tuple[dict[str, LibraryHit], set[str]]:
    """One hit per ref, from the indexed chunks; the refs split over several chunks.

    A search returns one chunk, but the result file keeps its ref only. For a
    section longer than one chunk the parts are joined, which is more than
    the model was shown; build counts those refs.
    """
    parts: dict[str, list[Any]] = defaultdict(list)
    for chunk in chunks:
        parts[chunk.ref].append(chunk)
    hits = {}
    for ref, found in parts.items():
        found.sort(key=lambda c: c.part)
        first = found[0]
        hits[ref] = LibraryHit(
            ref=ref,
            doc_id=first.doc_id,
            title=first.title,
            heading=first.heading,
            published_at=first.published_at,
            content="\n\n".join(c.content for c in found),
            score=0.0,
            reranker_score=None,
        )
    return hits, {ref for ref, found in parts.items() if len(found) > 1}


def replay(document: Mapping[str, Any], tools: CaseTools, hits: Mapping[str, LibraryHit]):
    """The (name, arguments, output) of each recorded tool call, as the model got them."""
    # The outputs are rebuilt from the evidence, so it has to be the run's.
    digest = hashlib.sha256(evidence_json(tools.evidence)).hexdigest()
    if digest != document["provenance"]["evidence_sha256"]:
        raise ReplayMismatch(f"{document.get('run_id')}: the evidence differs from the run's")
    calls = document["tool_calls"]
    withheld = {ref for call in calls for ref in call.get("withheld", [])}
    searches = iter([c for c in calls if c["name"] == "search_library"])

    def search(query: str, timeout: float | None = None) -> list[LibraryHit]:
        call = next(searches)
        # The withheld hits' places among the shown ones are not recorded;
        # they go last.
        return [hits[ref] for ref in [*call.get("refs", []), *call.get("withheld", [])]]

    tools.search = search
    # The screen ran during the run. Its withheld refs are set up front, so
    # the replay withholds the same items and screens nothing again.
    tools._flagged_refs = set(withheld)
    out = []
    for call in calls:
        arguments = {"query": call["query"]} if call["name"] == "search_library" else {}
        output = json.loads(tools.call(call["name"], json.dumps(arguments), timeout=60.0))
        recorded = {k: sorted(call.get(k, [])) for k in ("refs", "withheld")}
        replayed = {k: sorted(tools.last_call.get(k, [])) for k in ("refs", "withheld")}
        if call["name"] != "search_library":
            del recorded["refs"], replayed["refs"]
        if recorded != replayed:
            raise ReplayMismatch(f"{document.get('run_id')}: {call['name']} replayed differently")
        out.append((call["name"], arguments, output))
    return out


def tool_definitions(arm_name: str, deployment: str) -> list[dict]:
    tools = arm_definition(ARMS[arm_name], deployment)["tools"]
    return [{k: d[k] for k in ("type", "name", "description", "parameters")} for d in tools]


def rows(
    entries: Iterable[Mapping[str, Any]],
    load_run: Callable[[Mapping[str, Any]], dict],
    load_tools: Callable[[str], CaseTools],
    hits: Mapping[str, LibraryHit],
) -> tuple[list[dict], list[dict]]:
    """Quality rows (filled attempts of the evaluated repeats) and tool rows (agent arms)."""
    quality, tool_rows = [], []
    for entry in entries:
        if entry["status"] not in FILLED or entry["repeat"] not in REPEATS:
            continue
        document = load_run(entry)
        calls = replay(document, load_tools(entry["case_id"]), hits)
        answer = json.dumps(document["investigation"], ensure_ascii=False)
        base = {"run_id": entry["run_id"], "arm": entry["arm"], "case_id": entry["case_id"]}
        context = "\n\n".join(
            f"{name} returned:\n{json.dumps(output, ensure_ascii=False)}"
            for name, _, output in calls
        )
        quality.append(base | {"query": QUERY, "response": answer, "context": context})
        if ARMS[entry["arm"]].kind != "agent":
            continue
        messages: list[dict] = []
        for n, (name, arguments, output) in enumerate(calls, start=1):
            call_id = f"call_{n}"
            messages.append(
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_call",
                            "tool_call_id": call_id,
                            "name": name,
                            "arguments": arguments,
                        }
                    ],
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": [{"type": "tool_result", "tool_result": output}],
                }
            )
        messages.append({"role": "assistant", "content": answer})
        instructions = ARMS[entry["arm"]].prompt.read_text(encoding="utf-8")
        tool_rows.append(
            base
            | {
                "query": [
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": QUERY},
                ],
                "response": messages,
                "tool_definitions": tool_definitions(entry["arm"], document["model"]["deployment"]),
            }
        )
    return quality, tool_rows


def _verified_run(entry: Mapping[str, Any]) -> dict:
    return verified_run(entry, RUNS_DIR)


def _check_prompts(entries: Iterable[Mapping[str, Any]]) -> None:
    """Refuse when an arm's prompt now differs from the one its runs recorded."""
    from hindcast.evaluation.prior import committed_blob_hash

    for entry in entries:
        if entry["status"] not in FILLED:
            continue
        recorded = _verified_run(entry)["provenance"]["prompt"]
        now = committed_blob_hash(ARMS[entry["arm"]].prompt)
        if recorded.get("dirty") or recorded.get("blob") != now:
            raise ValueError(f"{entry['run_id']}: the arm's prompt changed since the run")


def build(out_dir: Path = OUT_DIR) -> list[str]:
    from hindcast import index
    from hindcast.cases import load_cases
    from hindcast.library import load_library
    from hindcast.tools import load_evidence

    entries = load_attempts(ATTEMPTS)
    _check_prompts(entries)
    cases = load_cases()
    library = load_library(Path("data/library.yaml"), cases)
    chunks = [
        chunk
        for doc_id, doc in sorted(library.items())
        for chunk in index.chunks(
            json.loads((index.EXTRACTS_DIR / f"{doc_id}.json").read_text("utf-8")), doc
        )
    ]
    hits, split = library_hits(chunks)

    def load_tools(case_id: str) -> CaseTools:
        return CaseTools(load_evidence(EVIDENCE_DIR / f"{case_id}.json"))

    quality, tool_rows = rows(entries, _verified_run, load_tools, hits)
    searched = {
        ref
        for e in entries
        if e["status"] in FILLED
        for c in _verified_run(e)["tool_calls"]
        for ref in c.get("refs", [])
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for dataset, data in zip(DATASETS, (quality, tool_rows), strict=True):
        path = out_dir / f"{dataset.name}.jsonl"
        text = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in data)
        path.write_text(text, encoding="utf-8")
        digest = hashlib.sha256(text.encode()).hexdigest()
        lines.append(f"{path}: {len(data)} rows, sha256 {digest}")
    lines.append(
        f"library refs searched: {len(searched)}, split over chunks: {len(searched & split)}"
    )
    return lines


def submit(out_dir: Path = OUT_DIR, record_dir: Path = RECORD_DIR) -> list[str]:
    from openai.types.eval_create_params import DataSourceConfigCustom
    from openai.types.evals.create_eval_jsonl_run_data_source_param import (
        CreateEvalJSONLRunDataSourceParam,
        SourceFileID,
    )

    from hindcast import models

    record_path = record_dir / "runs.json"
    if record_path.exists():
        raise FileExistsError(f"{record_path} exists: the evaluation was submitted already")
    project = models.project_client()
    client = models.openai_client()
    name, version = models.deployment_model(JUDGE_DEPLOYMENT)
    record: dict[str, Any] = {
        "judge": {"deployment": JUDGE_DEPLOYMENT, "name": name, "version": version},
        "submitted_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "evaluations": [],
    }
    lines = []
    for dataset in DATASETS:
        path = out_dir / f"{dataset.name}.jsonl"
        data = path.read_bytes()
        uploaded = project.datasets.upload_file(
            name=dataset.name, version=DATASET_VERSION, file_path=str(path)
        )
        evaluation = client.evals.create(
            name=dataset.name,
            data_source_config=DataSourceConfigCustom(
                type="custom", item_schema=item_schema(dataset)
            ),
            # Foundry's azure_ai_evaluator criterion is not among the openai
            # package's criterion types; the service defines it.
            testing_criteria=cast(Any, criteria_for(dataset)),
        )
        run = client.evals.runs.create(
            eval_id=evaluation.id,
            name=f"{dataset.name}-run",
            data_source=CreateEvalJSONLRunDataSourceParam(
                type="jsonl", source=SourceFileID(type="file_id", id=str(uploaded.id))
            ),
        )
        record["evaluations"].append(
            {
                "dataset": {
                    "name": dataset.name,
                    "version": DATASET_VERSION,
                    "rows": data.count(b"\n"),
                    "sha256": hashlib.sha256(data).hexdigest(),
                },
                "eval_id": evaluation.id,
                "run_id": run.id,
                "criteria": criteria_for(dataset),
            }
        )
        lines.append(f"{dataset.name}: eval {evaluation.id}, run {run.id}, status {run.status}")
    record_dir.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return lines


def _as_dict(value: Any) -> dict:
    return value.to_dict() if hasattr(value, "to_dict") else dict(value)


def aggregate(items: Iterable[Any], criteria: Iterable[str]) -> dict[str, dict[str, dict]]:
    """Per arm and evaluator: rows, passed, failed, errored, and the mean score.

    A row whose result for an evaluator is missing, has no score or no
    verdict, or carries an error counts as errored, not as a fail: the
    service's own counts once reported no errors while two judge calls had
    failed (#7).
    """
    table: dict[str, dict[str, dict]] = defaultdict(dict)
    names = tuple(criteria)
    for raw in items:
        item = _as_dict(raw)
        arm = (item.get("datasource_item") or {}).get("arm", "unknown")
        results = {r.get("name"): r for r in item.get("results") or []}
        for name in names:
            cell = table[arm].setdefault(
                name, {"rows": 0, "passed": 0, "failed": 0, "errored": 0, "scores": []}
            )
            cell["rows"] += 1
            result = results.get(name) or {}
            score, passed = result.get("score"), result.get("passed")
            if score is None or passed is None or (result.get("sample") or {}).get("error"):
                cell["errored"] += 1
                continue
            cell["passed" if passed else "failed"] += 1
            cell["scores"].append(float(score))
    for cells in table.values():
        for cell in cells.values():
            scores = cell.pop("scores")
            cell["mean_score"] = round(sum(scores) / len(scores), 3) if scores else None
    return {arm: dict(sorted(cells.items())) for arm, cells in sorted(table.items())}


def results(record_dir: Path = RECORD_DIR, poll_seconds: float = 30.0) -> list[str]:
    from hindcast import models

    client = models.openai_client()
    record = json.loads((record_dir / "runs.json").read_text("utf-8"))
    out: dict[str, Any] = {"judge": record["judge"], "evaluations": []}
    lines = []
    for evaluation in record["evaluations"]:
        while True:
            run = client.evals.runs.retrieve(evaluation["run_id"], eval_id=evaluation["eval_id"])
            if run.status in ("completed", "failed", "canceled"):
                break
            time.sleep(poll_seconds)
        items = list(
            client.evals.runs.output_items.list(evaluation["run_id"], eval_id=evaluation["eval_id"])
        )
        run_data = _as_dict(run)
        criteria = [c["name"] for c in evaluation["criteria"]]
        table = aggregate(items, criteria)
        out["evaluations"].append(
            {
                "dataset": evaluation["dataset"],
                "eval_id": evaluation["eval_id"],
                "run_id": evaluation["run_id"],
                "status": run.status,
                # The service's own counts, next to the per-row ones above.
                "result_counts": run_data.get("result_counts"),
                "per_testing_criteria_results": run_data.get("per_testing_criteria_results"),
                "output_items": len(items),
                "by_arm": table,
            }
        )
        lines.append(f"{evaluation['dataset']['name']}: {run.status}, {len(items)} rows")
        for arm, cells in table.items():
            for name, cell in cells.items():
                lines.append(
                    f"  {arm} {name}: passed {cell['passed']}, failed {cell['failed']}, "
                    f"errored {cell['errored']}, mean {cell['mean_score']}"
                )
    (record_dir / "results.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hindcast.evaluation.foundry")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build", help="write the datasets from the scored runs")
    commands.add_parser("submit", help="upload the datasets and start the evaluations")
    commands.add_parser("results", help="wait for the runs and write the counts")
    args = parser.parse_args(argv)
    run = {"build": build, "submit": submit, "results": results}[args.command]
    print("\n".join(run()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
