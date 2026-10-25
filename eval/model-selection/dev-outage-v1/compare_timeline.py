"""Ask one deployment for the development outage's timeline, for the hand count in the README.

    PYTHONPATH=src uv run --frozen --env-file .env \
        python eval/model-selection/dev-outage-v1/compare_timeline.py <deployment> <effort>

Writes the answer to data/sources/model-selection/ (ignored by Git: it repeats
Cloudflare's status text) and prints the token usage. A run is never repeated
over an existing answer.
"""

import json
import sys
from pathlib import Path

from build_dataset import SNAPSHOT, context

from hindcast.models import ask_model

OUT_DIR = Path("data/sources/model-selection")
SYSTEM = (
    "You read a provider's status updates for one outage. List every event they "
    "report, in order, one per line, starting with its UTC time. Use only what the "
    "updates state. Do not add causes, events, or times that are not in them."
)


def main() -> None:
    deployment, effort = sys.argv[1], sys.argv[2]
    out = OUT_DIR / f"timeline-{deployment}-{effort}.txt"
    if out.exists():
        sys.exit(f"{out} exists; a run is never repeated over an answer")
    incident = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    answer, usage = ask_model(deployment, SYSTEM, context(incident), effort=effort)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(answer + "\n", encoding="utf-8")
    print(f"{out}: {usage.input_tokens} input, {usage.output_tokens} output tokens")


if __name__ == "__main__":
    main()
