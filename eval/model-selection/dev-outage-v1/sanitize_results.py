"""Sanitize one Foundry evaluation run's downloads before they are committed.

    uv run --frozen python eval/model-selection/dev-outage-v1/sanitize_results.py luna|sol

Reads data/sources/model-selection/eval-<target>-dev-outage-v1-results.jsonl and
-user_logs.txt (the portal's "Download results" and "Download user logs") and writes
results-<target>-dev-outage-v1.jsonl and log-excerpt-<target>-dev-outage-v1.txt to this
folder. The status text the models were given is Cloudflare's: every copy of it becomes
"<context withheld>". Run and evaluation IDs become placeholders, and the resource and
project names read from .env become "<resource>". The rows are sorted by question;
answers, scores, and reasons are kept. The log excerpt keeps only the lines the findings
cite: fields an evaluator dropped, evaluator versions, and the chat completions fallback.

Exit code 1, with nothing written, when a copy of the status text or an identifier is
still in the output.
"""

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

from build_dataset import SNAPSHOT, context
from check_quotes import normalise

HERE = Path(__file__).parent
RAW_DIR = Path("data/sources/model-selection")
WITHHELD = "<context withheld>"
IDS = (
    (re.compile(r"evalrun_[0-9a-f]+"), "<run-id>"),
    (re.compile(r"\beval_[0-9a-f]{32}\b"), "<eval-id>"),
    (re.compile(r"chatcmpl-[A-Za-z0-9]+"), "<completion-id>"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"), "<uuid>"),
)
UPDATE_START = re.compile(r"\n\n(?=\[\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC\] )")
CITED = ("Removed [", "evaluatorId provided:", "falling back to chat completions")


def names_from_env(path: Path) -> tuple[str, ...]:
    """Resource names in the endpoint URLs of .env, and the project name in the project endpoint."""
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.partition("=")[2].strip()
        if match := re.match(r"https://([^./]+)[^/]*(?:/api/projects/([^/]+))?", value):
            names += [name for name in match.groups() if name]
    return tuple(dict.fromkeys(names))


def _name_pattern(names: tuple[str, ...]) -> re.Pattern | None:
    if not names:
        return None
    # Longest first, so a project name that is the front of the resource name
    # does not leave the rest behind. A hyphen may follow ("<name>-appinsights"
    # still names the resource); a letter or digit may not.
    alternatives = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    return re.compile(rf"(?<![A-Za-z0-9])(?:{alternatives})(?![A-Za-z0-9])")


def _escaped(text: str) -> list[str]:
    """The text as it appears raw, JSON-encoded once, and JSON-encoded twice, longest first."""
    once = {json.dumps(text, ensure_ascii=ascii_)[1:-1] for ascii_ in (True, False)}
    twice = {json.dumps(o, ensure_ascii=ascii_)[1:-1] for o in once for ascii_ in (True, False)}
    return sorted({text} | once | twice, key=len, reverse=True)


def _scrubber(context: str, names: tuple[str, ...]):
    copies = _escaped(context) if context else []
    name_pattern = _name_pattern(names)

    def scrub(text: str) -> str:
        for copy in copies:
            text = text.replace(copy, WITHHELD)
        for pattern, placeholder in IDS:
            text = pattern.sub(placeholder, text)
        return name_pattern.sub("<resource>", text) if name_pattern else text

    return scrub


def _map_strings(value, change):
    if isinstance(value, dict):
        return {k: _map_strings(v, change) for k, v in value.items()}
    if isinstance(value, list):
        return [_map_strings(v, change) for v in value]
    return change(value) if isinstance(value, str) else value


def sanitize_row(row: dict, context: str, names: tuple[str, ...]) -> dict:
    return _map_strings(row, _scrubber(context, names))


def _strings(value, path=""):
    """Every string with its path; a string that holds JSON is searched inside too."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value
        if value.startswith(("{", "[")):
            try:
                inner = json.loads(value)
            except json.JSONDecodeError:
                return
            # Inner strings are reported under the path of the field that holds them.
            yield from ((path, s) for _, s in _strings(inner))


def leaks(rows: list[dict], context: str) -> list[str]:
    """Fields that still share more text with the context than its longest single update.

    Answers quote updates, so a shared run up to one whole update is expected. A longer run
    spans two updates, which only a copy of the context gives, however it was reformatted.
    """
    # An update starts at its "[YYYY-MM-DD HH:MM UTC]" stamp (build_dataset.context);
    # a blank line alone can also sit inside one update.
    blocks = UPDATE_START.split(context)
    if len(blocks) < 2:
        raise ValueError("context has fewer than two updates: the leak check could not fail")
    updates = normalise(context)
    limit = max(len(normalise(block)) for block in blocks)
    found = []
    for row in rows:
        for path, text in _strings(row):
            text = normalise(text)
            if len(text) <= limit:
                continue
            match = difflib.SequenceMatcher(None, text, updates, autojunk=False)
            shared = match.find_longest_match(0, len(text), 0, len(updates)).size
            label = f"row {row['datasource_item_id']} {path}"
            if shared > limit and label not in found:
                found.append(label)
    return found


def identifiers(text: str, names: tuple[str, ...]) -> list[str]:
    """Run IDs, evaluation IDs, completion IDs, UUIDs, and resource names still in the text."""
    patterns = [pattern for pattern, _ in IDS]
    if pattern := _name_pattern(names):
        patterns.append(pattern)
    return sorted({m.group() for p in patterns for m in p.finditer(text)})


def log_excerpt(lines: list[str], names: tuple[str, ...]) -> list[str]:
    scrub = _scrubber("", names)
    return [scrub(line) for line in lines if any(c in line for c in CITED)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", choices=["luna", "sol"])
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    parser.add_argument("--env", type=Path, default=Path(".env"))
    parser.add_argument("--out-dir", type=Path, default=HERE)
    args = parser.parse_args()

    stem = f"{args.target}-dev-outage-v1"
    text = context(json.loads(args.snapshot.read_text(encoding="utf-8")))
    names = names_from_env(args.env)
    raw = args.raw_dir / f"eval-{stem}-results.jsonl"
    rows = [json.loads(line) for line in raw.open(encoding="utf-8")]
    clean = sorted(
        (sanitize_row(row, text, names) for row in rows), key=lambda r: r["datasource_item_id"]
    )
    log = (args.raw_dir / f"eval-{stem}-user_logs.txt").read_text(encoding="utf-8")
    excerpt = log_excerpt(log.splitlines(), names)

    lines = [json.dumps(row, ensure_ascii=False) for row in clean]
    left = identifiers("\n".join(lines + excerpt), names)
    problems = [f"status text in {label}" for label in leaks(clean, text)]
    problems += [f"identifier left: {value}" for value in left]
    if problems:
        print("\n".join(problems))
        print(f"{len(problems)} problems; nothing written")
        return 1
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / f"results-{stem}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    excerpt_text = "".join(line + "\n" for line in excerpt)
    (args.out_dir / f"log-excerpt-{stem}.txt").write_text(excerpt_text, encoding="utf-8")
    print(f"results-{stem}.jsonl: {len(lines)} rows; log-excerpt-{stem}.txt: {len(excerpt)} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
