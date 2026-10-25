"""Build the upload file for dataset dev-outage-v1 from the local status snapshot.

    uv run --frozen python eval/model-selection/dev-outage-v1/build_dataset.py

Writes data/sources/model-selection/dataset-dev-outage-v1.jsonl (ignored by
Git): each question with the development case's status updates as context.
The status text is Cloudflare's, so only the questions are committed.
"""

import json
from pathlib import Path

HERE = Path(__file__).parent
SNAPSHOT = Path("data/sources/cloudflare-2026-02-20/cloudflare-status-2026-02-20.json")
OUT = Path("data/sources/model-selection/dataset-dev-outage-v1.jsonl")


def context(incident: dict) -> str:
    """Every update before the resolved one, then the resolved update's time and status only."""
    lines = []
    for update in sorted(incident["incident_updates"], key=lambda u: u["created_at"]):
        stamp = update["created_at"][:16].replace("T", " ") + " UTC"
        # The resolved update is where providers put their summary of the cause,
        # so its text is withheld; its time and status stay.
        body = "(text withheld)" if update["status"] == "resolved" else update["body"].strip()
        lines.append(f"[{stamp}] {update['status']}: {body}")
    return "\n\n".join(lines)


def main() -> None:
    incident = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    text = context(incident)
    rows = []
    for line in (HERE / "questions-v1.jsonl").read_text(encoding="utf-8").splitlines():
        question = json.loads(line)
        rows.append(json.dumps(question | {"context": text}, ensure_ascii=False, sort_keys=True))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"{OUT}: {len(rows)} rows")


if __name__ == "__main__":
    main()
