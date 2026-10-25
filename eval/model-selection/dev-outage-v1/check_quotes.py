"""Check that every quote in each answer of an evaluation run appears word for word in the updates.

    uv run --frozen python eval/model-selection/dev-outage-v1/check_quotes.py RESULTS.jsonl \
        [--no-quote-ok N] [--break-row N]

A quote is text between curly double quotes in the model's answer. It counts as word for word
when it appears in the status text the models were given (rebuilt from the local snapshot,
because the committed results leave it out) after quote marks and whitespace are normalised
and trailing punctuation or an ellipsis is removed. Every answer needs a quote, except row N
given with --no-quote-ok: the question the updates cannot answer, where a refusal quotes
nothing. --break-row adds a word to the first quote of row N, to show the check fails on a
wrong quote. Exit code 1 when any quote is not found or a required quote is missing.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from build_dataset import SNAPSHOT, context

QUOTE = re.compile(r"“(.+?)”", re.DOTALL)


def normalise(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--no-quote-ok", type=int)
    parser.add_argument("--break-row", type=int)
    args = parser.parse_args()

    updates = normalise(context(json.loads(SNAPSHOT.read_text(encoding="utf-8"))))
    rows = [json.loads(line) for line in args.results.open(encoding="utf-8")]
    found = total = missing = 0
    for row in sorted(rows, key=lambda r: r["datasource_item_id"]):
        number = row["datasource_item_id"]
        quotes = QUOTE.findall(row["sample"]["output"][0]["content"])
        if number == args.break_row and quotes:
            quotes[0] = quotes[0] + " inserted"
        if not quotes:
            allowed = number == args.no_quote_ok
            missing += not allowed
            note = " (allowed: no answer in the updates)" if allowed else ""
            print(f"Q{number + 1}: no quote{note}")
        for quote in quotes:
            total += 1
            cut = quote.rstrip().endswith(("…", "..."))
            text = normalise(quote).rstrip(".,;:…").rstrip()
            ok = text in updates
            found += ok
            note = " (cut with an ellipsis)" if cut else ""
            print(f"Q{number + 1}: {'found' if ok else 'NOT FOUND'}{note}: {text[:70]}")
    print(f"{found} of {total} quotes word for word; {missing} answers missing a required quote")
    return 0 if found == total and missing == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
