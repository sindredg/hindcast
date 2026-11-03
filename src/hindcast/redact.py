"""PII masking of an investigation before it is written (decision 0007).

Every free-text field goes to PII detection (hindcast.safety). A hit is
replaced in the stored text by its category in brackets, and the result
lists each hit by field path, category, and confidence: never the text
found, so the record of a hit carries no personal data either. IDs, times,
refs, and the verdict are not free text and are not sent.
"""

from dataclasses import replace

from hindcast.result import Investigation, PiiFinding
from hindcast.safety import Pii, PiiHit

__all__ = ["PiiFinding", "mask", "redact_fields", "redact_investigation", "text_fields"]


def text_fields(investigation: Investigation) -> list[tuple[str, str]]:
    """Every free-text field with its path, in the result file's order."""
    i = investigation
    return [
        ("attack.reasoning", i.attack.reasoning),
        *((f"findings[{n}].claim", f.claim) for n, f in enumerate(i.findings)),
        *((f"timeline[{n}].event", t.event) for n, t in enumerate(i.timeline)),
        ("root_cause.claim", i.root_cause.claim),
        *(
            (f"contributing_factors[{n}].claim", f.claim)
            for n, f in enumerate(i.contributing_factors)
        ),
        *(
            field
            for n, q in enumerate(i.open_questions)
            for field in (
                (f"open_questions[{n}].question", q.question),
                (f"open_questions[{n}].why_open", q.why_open),
            )
        ),
    ]


def mask(text: str, hits: tuple[PiiHit, ...]) -> str:
    """Replace each hit by its category, right to left so earlier offsets stay valid.

    Overlapping hits are merged into one span named by every category in it,
    so no part of either is left in the text.
    """
    spans: list[list] = []
    for hit in sorted(hits, key=lambda h: h.offset):
        start, end = hit.offset, hit.offset + hit.length
        if spans and start < spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], end)
            spans[-1][2].add(hit.category)
        else:
            spans.append([start, end, {hit.category}])
    for start, end, categories in reversed(spans):
        text = f"{text[:start]}[{'/'.join(sorted(categories))}]{text[end:]}"
    return text


def redact_fields(
    fields: list[tuple[str, str]], pii: Pii, *, timeout: float
) -> tuple[dict[str, str], tuple[PiiFinding, ...]]:
    """The masked text of each field that had a hit, and every hit by path."""
    answers = pii([text for _, text in fields], timeout=timeout)
    masked: dict[str, str] = {}
    findings: list[PiiFinding] = []
    for (path, text), hits in zip(fields, answers, strict=True):
        if hits:
            masked[path] = mask(text, hits)
            findings += [PiiFinding(path, h.category, h.confidence) for h in hits]
    return masked, tuple(findings)


def redact_investigation(
    investigation: Investigation, pii: Pii, *, timeout: float
) -> tuple[Investigation, tuple[PiiFinding, ...]]:
    masked, findings = redact_fields(text_fields(investigation), pii, timeout=timeout)
    if not masked:
        return investigation, findings

    def get(path: str, text: str) -> str:
        return masked.get(path, text)

    i = investigation
    redacted = replace(
        i,
        attack=replace(i.attack, reasoning=get("attack.reasoning", i.attack.reasoning)),
        findings=tuple(
            replace(f, claim=get(f"findings[{n}].claim", f.claim)) for n, f in enumerate(i.findings)
        ),
        timeline=tuple(
            replace(t, event=get(f"timeline[{n}].event", t.event)) for n, t in enumerate(i.timeline)
        ),
        root_cause=replace(i.root_cause, claim=get("root_cause.claim", i.root_cause.claim)),
        contributing_factors=tuple(
            replace(f, claim=get(f"contributing_factors[{n}].claim", f.claim))
            for n, f in enumerate(i.contributing_factors)
        ),
        open_questions=tuple(
            replace(
                q,
                question=get(f"open_questions[{n}].question", q.question),
                why_open=get(f"open_questions[{n}].why_open", q.why_open),
            )
            for n, q in enumerate(i.open_questions)
        ),
    )
    return redacted, findings
