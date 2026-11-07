"""The judge: an outcome per key item and a support verdict per run item, for review.

    PYTHONPATH=src uv run --frozen python -m hindcast.evaluation.judge freeze
    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.evaluation.judge \
        one <result file> --out <judgment file>
    PYTHONPATH=src uv run --frozen --env-file .env python -m hindcast.evaluation.judge run

The judge is claude-opus-5-5 on the Anthropic API (decision 0024): a model
family no scored arm uses. It proposes; the review decides (rubric version 2,
Review). It reads one run at a time: the key items, the run's items after the
code's citation checks, and the text of every update, chart, and library item
the run cites (hindcast.excerpts). It does not see the run's arm, its model,
or the key items' labels: the outcomes do not depend on them, and the score
applies the labels afterwards.

The reply follows one fixed JSON schema: a list of run items with their
support verdicts and a list of key items with their outcomes. The code then
checks that it names every key item and every run item exactly once, gives
each key item an outcome the rubric allows for it, and leaves the code's
unsupported items unsupported; a reply that fails is a schema error. A
refusal, an empty reply, a reply cut at max_tokens, a schema error, or a
reply whose outcomes contradict its own support verdicts is recorded as a
judge error for that run, never read as a verdict; `run` judges an errored
run again on its next call and keeps every judgment it already has.

No server-side fallback is sent: a fallback would let another model judge
some runs. `run` refuses unless the prompt and the rubric match
eval/judge/frozen.json, and prints counts and token usage only.
"""

import argparse
import hashlib
import json
import tempfile
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema

from hindcast.evaluation.batch import FILLED, ROOT, load_attempts, run_loader
from hindcast.evidence import CaseEvidence, evidence_json
from hindcast.excerpts import resolve
from hindcast.keys import AnswerKey
from hindcast.labels import item_ids
from hindcast.result import Citation

JUDGE_MODEL = "claude-opus-5-5"
EFFORT = "high"
# Thinking counts against max_tokens; a reply cut there is a judge error, so
# the cap sits well above a judgment's length. Streaming keeps a long reply
# under the SDK's request timeout.
MAX_TOKENS = 64000
PROMPT = Path("prompts/judge.md")
RUBRIC = Path("eval/rubric/rubric.md")
FROZEN = Path("eval/judge/frozen.json")
OUT_DIR = ROOT / "judgments"
KEYS_DIR = Path("eval/keys")
EVIDENCE_DIR = Path("build/evidence")
CLEAN_PATHS = (
    "src",
    "prompts",
    "eval/rubric",
    "eval/judge",
    "eval/keys",
    "pyproject.toml",
    "uv.lock",
)

# The outcomes rubric version 2 allows per kind of key item: partial only for
# a root cause or a factor, abstained only for a root cause or an attack verdict.
OUTCOMES = {
    "attack": ("supported-hit", "unsupported-hit", "abstained", "missed", "wrong"),
    "root_cause": (
        "supported-hit",
        "partial",
        "unsupported-hit",
        "unsupported-partial",
        "abstained",
        "missed",
        "wrong",
    ),
    "contributing_factors": (
        "supported-hit",
        "partial",
        "unsupported-hit",
        "unsupported-partial",
        "missed",
        "wrong",
    ),
    "timeline": ("supported-hit", "unsupported-hit", "missed", "wrong"),
}
NEEDS_SUPPORT = frozenset({"supported-hit", "partial"})
WITHOUT_SUPPORT = frozenset({"unsupported-hit", "unsupported-partial"})
_STRING = {"type": "string"}


class JudgeError(Exception):
    """A reply that is not a judgment: refusal, empty, cut, schema, or inconsistent."""

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


class NotFrozen(RuntimeError):
    """The judge prompt or the rubric differs from eval/judge/frozen.json."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def system_prompt(prompt: Path = PROMPT, rubric: Path = RUBRIC) -> str:
    """The judge prompt, then the rubric's outcome, matching, and support rules.

    The rubric's credit and review sections stay out: the judge proposes
    outcomes, it does not score them.
    """
    text = rubric.read_text(encoding="utf-8")
    title = text.split("\n", 1)[0]
    start, end = text.index("\n## Outcomes\n"), text.index("\n## Credit\n")
    return f"{prompt.read_text(encoding='utf-8').rstrip()}\n\n{title}\n{text[start:end].rstrip()}\n"


Compose = Callable[[Path, Path], str]


def _frozen_record(prompt: Path, rubric: Path, compose: Compose, model: str) -> dict:
    system = compose(prompt, rubric)
    return {
        "prompt": prompt.as_posix(),
        "prompt_sha256": _sha256(prompt.read_bytes()),
        "rubric": rubric.as_posix(),
        "rubric_sha256": _sha256(rubric.read_bytes()),
        "system_sha256": _sha256(system.encode()),
        "model": model,
        "effort": EFFORT,
        "max_tokens": MAX_TOKENS,
    }


def freeze(
    prompt: Path = PROMPT,
    rubric: Path = RUBRIC,
    frozen: Path = FROZEN,
    compose: Compose = system_prompt,
    model: str = JUDGE_MODEL,
) -> dict:
    """Write the lock. A new version replaces the file in its own commit."""
    if frozen.exists():
        raise FileExistsError(f"{frozen} exists; a new judge version replaces it deliberately")
    record = _frozen_record(prompt, rubric, compose, model)
    record["frozen_at"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    frozen.parent.mkdir(parents=True, exist_ok=True)
    frozen.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def check_frozen(
    prompt: Path = PROMPT,
    rubric: Path = RUBRIC,
    frozen: Path = FROZEN,
    compose: Compose = system_prompt,
    model: str = JUDGE_MODEL,
) -> str:
    """The system prompt, or NotFrozen when it or the settings differ from the lock."""
    if not frozen.is_file():
        raise NotFrozen(f"{frozen} is missing: freeze the judge prompt first")
    record = json.loads(frozen.read_text(encoding="utf-8"))
    record.pop("frozen_at", None)
    if record != _frozen_record(prompt, rubric, compose, model):
        raise NotFrozen(f"the judge prompt, the rubric, or the settings differ from {frozen}")
    return compose(prompt, rubric)


def locked_rubric(rubric: Path, rubric_sha256: str, repo: Path = Path(".")) -> bytes:
    """The committed version of the rubric whose SHA-256 the lock records."""
    from hindcast.evaluation.prior import _git

    listing = _git(repo, "log", "--format=%H", "--", rubric.as_posix())
    if listing.returncode != 0:
        raise NotFrozen(f"cannot read the history of {rubric}")
    for commit in listing.stdout.split():
        shown = _git(repo, "show", f"{commit}:{rubric.as_posix()}")
        if shown.returncode == 0 and _sha256(shown.stdout.encode()) == rubric_sha256:
            return shown.stdout.encode()
    raise NotFrozen(f"no committed version of {rubric} has the locked hash {rubric_sha256[:12]}")


def check_frozen_or_locked(
    prompt: Path = PROMPT,
    rubric: Path = RUBRIC,
    frozen: Path = FROZEN,
    compose: Compose = system_prompt,
    model: str = JUDGE_MODEL,
) -> str:
    """check_frozen, or the locked system prompt rebuilt from the rubric version it names.

    The judge was frozen under rubric version 2; version 3 changed only the
    title and the Review section, after the judge ran. A later run, such as a
    revealed seal, is judged with exactly the system prompt the showcase runs
    were: rebuilt from the locked rubric in the history and accepted only when
    its hash, the prompt's hash, and the settings match the lock.
    """
    try:
        return check_frozen(prompt, rubric, frozen, compose, model)
    except NotFrozen:
        # No lock at all: nothing to rebuild from.
        if not frozen.is_file():
            raise
    record = json.loads(frozen.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as folder:
        old = Path(folder) / rubric.name
        old.write_bytes(locked_rubric(rubric, record["rubric_sha256"]))
        system = compose(prompt, old)
        # The record holds the system prompt's hash, so equal records mean the same prompt.
        rebuilt = _frozen_record(prompt, old, compose, model) | {"rubric": rubric.as_posix()}
    record.pop("frozen_at", None)
    if rebuilt != record:
        raise NotFrozen(f"the judge prompt or the settings differ from {frozen}")
    return system


def locked_system(prompt: Path = PROMPT, frozen: Path = FROZEN) -> tuple[str, str]:
    """The locked system prompt's hash and model, for checking judgments already made.

    A judgment records the hash of the system prompt it was given. Checking
    that hash against the lock, not against a prompt composed again from the
    rubric, keeps a judgment valid after a rubric version that changes no
    rule the judge reads: the rubric's title line is in the system prompt.
    The prompt file still has to match the lock.
    """
    if not frozen.is_file():
        raise NotFrozen(f"{frozen} is missing")
    record = json.loads(frozen.read_text(encoding="utf-8"))
    if record["prompt"] != prompt.as_posix() or record["prompt_sha256"] != _sha256(
        prompt.read_bytes()
    ):
        raise NotFrozen(f"{prompt} differs from {frozen}")
    return record["system_sha256"], record["model"]


def run_items(investigation: Mapping[str, Any]) -> list[dict]:
    """The run's scored items in order, each with the kind its support rule follows.

    A finding keeps the kind the run declared; a timeline event is an
    observation when its time is stated and an inference when worked out.
    The attack verdict, the root cause, and the factors are conclusions the
    run draws, so they are judged as inferences.
    """

    def refs(item: Mapping[str, Any]) -> list[str]:
        return [c["ref"] for c in item["citations"]]

    attack = investigation["attack"]
    items = [
        {
            "where": "attack",
            "kind": "inference",
            "text": f"Verdict: {attack['verdict']}. {attack['reasoning']}",
            "rests_on": [],
            "citations": refs(attack),
        }
    ]
    for n, f in enumerate(investigation["findings"]):
        items.append(
            {
                "where": f"findings[{n}]",
                "id": f["id"],
                "kind": f["kind"],
                "text": f["claim"],
                "rests_on": f["rests_on"],
                "citations": refs(f),
            }
        )
    for n, t in enumerate(investigation["timeline"]):
        items.append(
            {
                "where": f"timeline[{n}]",
                "kind": "observation" if t["time_kind"] == "stated" else "inference",
                "text": f"{t['time']} ({t['time_kind']} time): {t['event']}",
                "rests_on": [],
                "citations": refs(t),
            }
        )
    root = investigation["root_cause"]
    items.append(
        {
            "where": "root_cause",
            "kind": "inference",
            "text": root["claim"],
            "rests_on": root["rests_on"],
            "citations": refs(root),
        }
    )
    for n, f in enumerate(investigation["contributing_factors"]):
        items.append(
            {
                "where": f"contributing_factors[{n}]",
                "kind": "inference",
                "text": f["claim"],
                "rests_on": f["rests_on"],
                "citations": refs(f),
            }
        )
    return items


def key_items(key: AnswerKey) -> list[dict]:
    items: list[dict] = [
        {"id": "attack", "text": key.attack, "quote": key.attack_quote},
        {"id": "root_cause", "text": key.root_cause.text, "quote": key.root_cause.source_quote},
    ]
    items += [
        {"id": f"contributing_factors/{n}", "text": f.text, "quote": f.source_quote}
        for n, f in enumerate(key.contributing_factors)
    ]
    items += [
        {
            "id": f"timeline/{n}",
            "time": e.time,
            "time_as_written": e.time_as_written,
            "text": e.event,
            "quote": e.source_quote,
        }
        for n, e in enumerate(key.timeline)
    ]
    if [i["id"] for i in items] != item_ids(key):
        raise ValueError(f"{key.case_id}: key item IDs differ from hindcast.labels.item_ids")
    return items


def judge_input(
    document: Mapping[str, Any],
    key: AnswerKey,
    evidence: CaseEvidence,
    library: Mapping[str, dict],
) -> str:
    """The user message: the case, the key items, the run's items, and the cited text."""
    run_id = document.get("run_id")
    if _sha256(evidence_json(evidence)) != document["provenance"]["evidence_sha256"]:
        raise ValueError(f"{run_id}: the evidence differs from the run's")
    if document["case_id"] != key.case_id or evidence.case_id != key.case_id:
        raise ValueError(f"{run_id}: the run, the key, and the evidence name other cases")
    investigation = document["investigation"]
    cited: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for part in ("attack", "findings", "timeline", "root_cause", "contributing_factors"):
        value = investigation[part]
        for item in value if isinstance(value, list) else [value]:
            for c in item["citations"]:
                if (c["source"], c["ref"]) in seen:
                    continue
                seen.add((c["source"], c["ref"]))
                excerpt = resolve(Citation(c["source"], c["ref"]), evidence, library)
                if excerpt is None:
                    raise ValueError(f"{run_id}: cannot resolve the citation {c['ref']}")
                cited.append(
                    {
                        "ref": excerpt.ref,
                        "source": excerpt.source,
                        "title": excerpt.title,
                        "text": excerpt.text,
                    }
                )
    data = {
        "case": {
            "provider": evidence.provider,
            "title": evidence.title,
            "started_at": evidence.started_at,
        },
        "key_items": key_items(key),
        "run_items": run_items(investigation),
        "open_questions": investigation["open_questions"],
        "code_unsupported": list(document["checks"]["unsupported"]),
        "cited": cited,
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def _object(properties: dict[str, Any]) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def judgment_schema() -> dict:
    """The reply's schema, the same for every run: a list of run items and of key items.

    A schema that named each item of the run was refused by the API (HTTP 400,
    compiled grammar too large): the grammar grew with every key item's list
    of run items, past the limit at 15 key items. read_reply checks what that
    schema enforced.
    """
    run_item = _object({"where": _STRING, "reason": _STRING, "supported": {"type": "boolean"}})
    key_item = _object(
        {
            "id": _STRING,
            "run_items": {"type": "array", "items": _STRING},
            "reason": _STRING,
            "outcome": {"type": "string", "enum": list(OUTCOMES["root_cause"])},
        }
    )
    return _object(
        {
            "run_items": {"type": "array", "items": run_item},
            "key_items": {"type": "array", "items": key_item},
        }
    )


def _keyed(entries: list[dict], name: str, expected: list[str]) -> dict[str, dict]:
    """The reply's list keyed by item; each expected item exactly once, or a schema error."""
    keyed = {e[name]: {k: v for k, v in e.items() if k != name} for e in entries}
    if len(keyed) != len(entries) or set(keyed) != set(expected):
        raise JudgeError("schema")
    return {item: keyed[item] for item in expected}


def _check_fits(data: Mapping[str, Any], code_unsupported: set[str]) -> None:
    """What a per-run schema would enforce: outcomes the rubric allows, code verdicts kept."""
    for item, verdict in data["key_items"].items():
        if verdict["outcome"] not in OUTCOMES[item.split("/")[0]]:
            raise JudgeError("schema")
        if not set(verdict["run_items"]) <= data["run_items"].keys():
            raise JudgeError("schema")
    if any(data["run_items"][w]["supported"] for w in code_unsupported):
        raise JudgeError("schema")


def _check_consistent(data: Mapping[str, Any]) -> None:
    support = {w: v["supported"] for w, v in data["run_items"].items()}
    for verdict in data["key_items"].values():
        listed, outcome = verdict["run_items"], verdict["outcome"]
        if (outcome == "missed") == bool(listed):
            raise JudgeError("inconsistent")
        if outcome in NEEDS_SUPPORT and not any(support[w] for w in listed):
            raise JudgeError("inconsistent")
        if outcome in WITHOUT_SUPPORT and any(support[w] for w in listed):
            raise JudgeError("inconsistent")


def read_json(message: Any, schema: dict) -> dict:
    """The JSON in a reply, or JudgeError; the stop reason is read before the text."""
    stop = message.stop_reason
    if stop == "refusal":
        raise JudgeError("refusal")
    if stop == "max_tokens":
        raise JudgeError("max-tokens")
    if stop != "end_turn":
        raise JudgeError(f"stop-{stop}")
    text = "".join(block.text for block in message.content if block.type == "text")
    if not text.strip():
        raise JudgeError("empty")
    try:
        data = json.loads(text)
        jsonschema.validate(data, schema, cls=jsonschema.Draft202012Validator)
    except (json.JSONDecodeError, jsonschema.ValidationError) as error:
        raise JudgeError("schema") from error
    return data


def read_reply(
    message: Any, items: list[dict], key_ids: list[str], code_unsupported: set[str]
) -> dict:
    """A reconstruction's judgment, keyed by item: every item once, outcomes that fit.

    The judgment is stored keyed by key item ID and by run item `where`, in
    the run's and the key's order.
    """
    reply = read_json(message, judgment_schema())
    data = {
        "run_items": _keyed(reply["run_items"], "where", [i["where"] for i in items]),
        "key_items": _keyed(reply["key_items"], "id", key_ids),
    }
    _check_fits(data, code_unsupported)
    _check_consistent(data)
    return data


def new_record(system: str, content: str, model: str = JUDGE_MODEL) -> dict[str, Any]:
    return {
        "judge": {
            "model": model,
            "effort": EFFORT,
            "max_tokens": MAX_TOKENS,
            "system_sha256": _sha256(system.encode()),
            "input_sha256": _sha256(content.encode()),
            "judged_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "request_id": None,
            "response_model": None,
        },
        "stop_reason": None,
        "usage": None,
        "judgment": None,
        "error": None,
    }


def call(
    client: Any,
    system: str,
    content: str,
    schema: dict,
    record: dict[str, Any],
    read: Callable[[Any], dict],
    model: str = JUDGE_MODEL,
) -> dict[str, Any]:
    """One streamed judge call; the record gets the reply's judgment or its error kind."""
    with client.messages.stream(
        model=model,
        max_tokens=MAX_TOKENS,
        # The same system prompt opens every call; caching it is the only
        # repeated prefix.
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": content}],
        thinking={"type": "adaptive"},
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": schema}},
    ) as stream:
        message = stream.get_final_message()
        record["judge"]["request_id"] = stream.request_id
    record["judge"]["response_model"] = message.model
    record["stop_reason"] = message.stop_reason
    details = getattr(message, "stop_details", None)
    if details is not None:
        record["stop_category"] = getattr(details, "category", None)
    usage = message.usage
    record["usage"] = {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_creation_input_tokens": usage.cache_creation_input_tokens or 0,
        "cache_read_input_tokens": usage.cache_read_input_tokens or 0,
    }
    try:
        record["judgment"] = read(message)
    except JudgeError as error:
        record["error"] = error.kind
    return record


def judge_run(
    document: Mapping[str, Any],
    key: AnswerKey,
    evidence: CaseEvidence,
    library: Mapping[str, dict],
    *,
    client: Any,
    system: str,
    model: str = JUDGE_MODEL,
) -> dict:
    """One judge call for one run; the record holds a judgment or an error, never both."""
    items = run_items(document["investigation"])
    code_unsupported = set(document["checks"]["unsupported"])
    content = judge_input(document, key, evidence, library)
    key_ids = item_ids(key)
    record: dict[str, Any] = {
        "run_id": document["run_id"],
        "case_id": document["case_id"],
        "kinds": {i["where"]: i["kind"] for i in items},
        "code_unsupported": sorted(code_unsupported),
        **new_record(system, content, model),
    }
    return call(
        client,
        system,
        content,
        judgment_schema(),
        record,
        lambda m: read_reply(m, items, key_ids, code_unsupported),
        model,
    )


def judgment_path(out_dir: Path, run_id: str) -> Path:
    return out_dir / f"{run_id}.json"


def judge_all(
    entries: Iterable[Mapping[str, Any]],
    *,
    load_run: Callable[[Mapping[str, Any]], dict],
    load_case: Callable[[str], tuple[AnswerKey, CaseEvidence]],
    library: Mapping[str, dict],
    client: Any,
    out_dir: Path = OUT_DIR,
    paths: tuple[Path, Path, Path] = (PROMPT, RUBRIC, FROZEN),
    workers: int = 1,
    stamp: Mapping[str, Any] | None = None,
    model: str = JUDGE_MODEL,
) -> dict[str, int]:
    """Judge every filled attempt that has no judgment yet; no-result attempts are never judged."""
    system = check_frozen_or_locked(*paths, model=model)
    counts = {"judged": 0, "errors": 0, "kept": 0}
    todo: list[tuple[Mapping[str, Any], list[str]]] = []
    for entry in entries:
        if entry["status"] not in FILLED:
            continue
        path = judgment_path(out_dir, entry["run_id"])
        earlier: list[str] = []
        if path.exists():
            old = json.loads(path.read_text(encoding="utf-8"))
            if old["error"] is None:
                counts["kept"] += 1
                continue
            earlier = [*old.get("earlier_errors", []), old["error"]]
        todo.append((entry, earlier))

    def one(job: tuple[Mapping[str, Any], list[str]]) -> str | None:
        entry, earlier = job
        key, evidence = load_case(entry["case_id"])
        record = judge_run(
            load_run(entry), key, evidence, library, client=client, system=system, model=model
        )
        record |= {"arm": entry.get("arm"), "run_sha256": entry.get("sha256"), **(stamp or {})}
        record["earlier_errors"] = earlier
        path = judgment_path(out_dir, entry["run_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", "utf-8")
        return record["error"]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for error in pool.map(one, todo):
            counts["errors" if error else "judged"] += 1
    return counts


def load_case(case_id: str) -> tuple[AnswerKey, CaseEvidence]:
    """The frozen key, refused when it differs from its hash, and the case's evidence."""
    from hindcast.keys import FROZEN as KEYS_FROZEN
    from hindcast.keys import load_key
    from hindcast.tools import load_evidence

    path = KEYS_DIR / f"{case_id}.json"
    frozen = json.loads(KEYS_FROZEN.read_text(encoding="utf-8"))
    if _sha256(path.read_bytes()) != frozen.get(case_id):
        raise ValueError(f"{path} differs from its frozen hash")
    return load_key(path), load_evidence(EVIDENCE_DIR / f"{case_id}.json")


def _usage_line(records: Iterable[Mapping[str, Any]]) -> str:
    totals: dict[str, int] = {}
    for record in records:
        for name, value in (record.get("usage") or {}).items():
            totals[name] = totals.get(name, 0) + value
    return ", ".join(f"{name} {value}" for name, value in sorted(totals.items()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hindcast.evaluation.judge")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("freeze", help="write eval/judge/frozen.json")
    one = commands.add_parser("one", help="judge one result file (a test call)")
    one.add_argument("result", type=Path)
    one.add_argument("--out", type=Path, required=True)
    run = commands.add_parser("run", help="judge every filled scored run")
    run.add_argument("--workers", type=int, default=4)
    run.add_argument("--root", type=Path, default=ROOT, help=f"the scoring tree (default {ROOT})")
    args = parser.parse_args(argv)
    if args.command == "freeze":
        record = freeze()
        print(f"{FROZEN}: system sha256 {record['system_sha256']}")
        return 0

    import anthropic

    from hindcast.evaluation.prior import clean_head_commit
    from hindcast.excerpts import load_library_items

    # The code, prompt, rubric, keys, and lock that shape a judgment, committed.
    stamp = {"code_commit": clean_head_commit([Path(p) for p in CLEAN_PATHS])}
    client = anthropic.Anthropic()
    library = load_library_items()
    if args.command == "one":
        system = check_frozen_or_locked()
        document = json.loads(args.result.read_text(encoding="utf-8"))
        document.setdefault("run_id", args.result.stem)
        key, evidence = load_case(document["case_id"])
        record = judge_run(document, key, evidence, library, client=client, system=system)
        record |= stamp
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", "utf-8")
        print(f"{args.out}: error {record['error']}, stop {record['stop_reason']}")
        print(f"usage: {_usage_line([record])}")
        return 0
    out_dir = args.root / "judgments"
    counts = judge_all(
        load_attempts(args.root / "attempts.json"),
        load_run=run_loader(args.root),
        load_case=load_case,
        library=library,
        client=client,
        out_dir=out_dir,
        workers=args.workers,
        stamp=stamp,
    )
    records = [json.loads(p.read_text("utf-8")) for p in sorted(out_dir.rglob("*.json"))]
    errors = sorted({r["error"] for r in records if r["error"]})
    print(f"judged {counts['judged']}, errors {counts['errors']}, kept {counts['kept']}")
    print(f"judgment files {len(records)}, error kinds: {', '.join(errors) or 'none'}")
    print(f"usage over all judgment files: {_usage_line(records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
