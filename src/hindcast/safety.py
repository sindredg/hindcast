"""Prompt Shields and PII detection on the Foundry resource, over plain REST.

Decision 0007 puts Prompt Shields on every tool item before the model reads
it and PII detection on every output before it is written. Both services sit
on the project's Foundry resource and take the developer's Entra token; no
key is read.

No SDK covers Prompt Shields, and the Language SDK would be a second client
for one request shape, so both calls are hand-written on azure-core's
pipeline: a bearer-token policy and no retry policy. A retry would run past
the investigation's time budget, the same reason the model calls run without
one (hindcast.investigate).

An error names the HTTP status and the service's error code, never the
message: a service message can quote the principal or the request.
"""

import math
import time
from bisect import bisect_right
from collections.abc import Callable
from dataclasses import dataclass
from itertools import accumulate
from typing import Any, Protocol

from hindcast.config import SafetySettings

SCOPE = "https://cognitiveservices.azure.com/.default"
# Prompt Shields GA version; its limits per call. The character limit counts
# UTF-16 units: live on 2026-11-04 the service refused a document of 9,990
# code points that was 10,217 units and accepted one of 9,990 units (#54).
SHIELD_API_VERSION = "2024-09-01"
MAX_DOCUMENTS = 5
MAX_CHARACTERS = 10_000
# Text PII: newest GA API and model version, read from the Language
# model-lifecycle page on 2026-11-03. The sync limit is 5 documents of 5,120
# text elements each; a text element is one or more code points, so 5,000
# code points always fits.
PII_API_VERSION = "2026-05-01"
PII_MODEL_VERSION = "2026-05-01"
PII_MAX_DOCUMENTS = 5
PII_MAX_CHARACTERS = 5_000
# Billing counts a text record per started 1,000 characters of a document: the
# unit Language states, assumed for Prompt Shields until compared with the bill.
RECORD_CHARACTERS = 1_000
# The service's default categories, minus what is not personal data in an
# outage investigation: roles ("the on-call engineer"), companies and
# products, times, service hostnames and URLs, and public service addresses.
NOT_PERSONAL = frozenset({"PersonType", "Organization", "DateTime", "URL", "IPAddress"})


class ServiceError(RuntimeError):
    """A Prompt Shields or Language call that did not succeed."""


class ScreenError(RuntimeError):
    """Prompt Shields could not screen a text: the run must not go on unscreened."""


class PiiError(RuntimeError):
    """PII detection could not check a text: it must not be written unchecked."""


class Post(Protocol):
    def __call__(self, path: str, body: dict, *, timeout: float) -> dict: ...


def rest_post(endpoint: str, *, credential: Any = None, transport: Any = None) -> Post:
    """POST JSON to the resource with an Entra token; raise ServiceError on any failure."""
    from azure.core import PipelineClient
    from azure.core.exceptions import (
        AzureError,
        ServiceRequestTimeoutError,
        ServiceResponseTimeoutError,
    )
    from azure.core.pipeline.policies import BearerTokenCredentialPolicy
    from azure.core.rest import HttpRequest

    if credential is None:
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
    # No RetryPolicy in the list: one request per call.
    client = PipelineClient(
        endpoint, policies=[BearerTokenCredentialPolicy(credential, SCOPE)], transport=transport
    )
    base = endpoint.rstrip("/")

    def post(path: str, body: dict, *, timeout: float) -> dict:
        request = HttpRequest("POST", base + path, json=body)
        try:
            response = client.send_request(
                request, connection_timeout=timeout, read_timeout=timeout
            )
        except (ServiceRequestTimeoutError, ServiceResponseTimeoutError) as error:
            raise TimeoutError(f"{type(error).__name__} after {timeout:.1f}s") from error
        except AzureError as error:
            # Transport and credential errors alike; only the type, since a
            # credential's message can name the principal.
            raise ServiceError(type(error).__name__) from error
        try:
            data = response.json()
        except ValueError:
            data = None
        if not 200 <= response.status_code < 300:
            error = data.get("error") if isinstance(data, dict) else None
            code = error.get("code") if isinstance(error, dict) else None
            raise ServiceError(f"HTTP {response.status_code} {code or 'no error code'}")
        if not isinstance(data, dict):
            raise ServiceError(f"HTTP {response.status_code} body is not a JSON object")
        return data

    return post


def pieces(text: str, limit: int = MAX_CHARACTERS) -> list[str]:
    """Split text into pieces of at most limit characters, at a space where one is near."""
    out: list[str] = []
    while len(text) > limit:
        cut = text.rfind(" ", limit // 2, limit)
        # The space stays at the end of the earlier piece, so the pieces
        # join back to the text and offsets add up.
        cut = limit if cut < 0 else cut + 1
        out.append(text[:cut])
        text = text[cut:]
    return [*out, text]


# An instruction shorter than this lies whole inside one screened piece.
SCREEN_OVERLAP = 1_000


def utf16_units(text: str) -> int:
    """The length Prompt Shields counts: two units for a character outside the BMP."""
    return len(text) + sum(1 for c in text if ord(c) > 0xFFFF)


def screen_pieces(
    text: str, limit: int = MAX_CHARACTERS, overlap: int = SCREEN_OVERLAP
) -> list[str]:
    """Pieces for Prompt Shields: each starts `overlap` characters before the last one ended.

    Pieces cut end to end let an instruction across a cut reach the service
    in two halves, and either half may pass (#50). A text is flagged when
    any piece is, so the overlap costs only records. Each piece holds at
    most `limit` UTF-16 units (#54). PII detection keeps pieces(), whose
    offsets have to add up.
    """
    # units[i] is the UTF-16 length of text[:i].
    units = list(accumulate((2 if ord(c) > 0xFFFF else 1 for c in text), initial=0))
    out: list[str] = []
    start = 0
    while units[-1] - units[start] > limit:
        end = bisect_right(units, units[start] + limit) - 1
        if end - overlap <= start:
            raise ValueError(f"a piece of {limit} units cannot hold an overlap of {overlap}")
        out.append(text[start:end])
        start = end - overlap
    return [*out, text[start:]]


def batches(documents: list[str]) -> list[list[str]]:
    """Group documents in order, each group within Prompt Shields' per-call limits."""
    out: list[list[str]] = []
    current: list[str] = []
    size = 0
    for document in documents:
        length = utf16_units(document)
        if length > MAX_CHARACTERS:
            raise ValueError(f"a document of {length} UTF-16 units is over the limit")
        if current and (len(current) == MAX_DOCUMENTS or size + length > MAX_CHARACTERS):
            out.append(current)
            current, size = [], 0
        current.append(document)
        size += length
    return [*out, current] if current else out


def _deadline(timeout: float, clock: Callable[[], float]) -> Callable[[], float]:
    end = clock() + timeout

    def left() -> float:
        remaining = end - clock()
        if remaining <= 0:
            raise TimeoutError("no time left for the call")
        return remaining

    return left


class Shield(Protocol):
    calls: int
    records: int

    def documents(self, texts: list[str], *, timeout: float) -> list[bool]: ...

    def prompt(self, text: str, *, timeout: float) -> bool: ...


class PromptShield:
    """Prompt Shields. One flag per text; a text split into pieces is flagged if any piece is."""

    def __init__(self, post: Post, clock: Callable[[], float] = time.monotonic) -> None:
        self.post = post
        self.clock = clock
        self.calls = 0
        # Text records sent, for the cost: billing counts one per started
        # 1,000 characters of each document and of the prompt.
        self.records = 0

    def _call(
        self, user_prompt: str, documents: list[str], timeout: float
    ) -> tuple[bool, list[bool]]:
        try:
            data = self.post(
                f"/contentsafety/text:shieldPrompt?api-version={SHIELD_API_VERSION}",
                {"userPrompt": user_prompt, "documents": documents},
                timeout=timeout,
            )
        except ServiceError as error:
            raise ScreenError(str(error)) from error
        self.calls += 1
        self.records += sum(
            math.ceil(len(t) / RECORD_CHARACTERS) for t in [user_prompt, *documents]
        )
        analysis = data.get("documentsAnalysis")
        if not isinstance(analysis, list) or len(analysis) != len(documents):
            raise ScreenError("Prompt Shields answered for a different number of documents")
        flags = [a.get("attackDetected") for a in analysis if isinstance(a, dict)]
        # The service omits userPromptAnalysis for an empty prompt; for a real
        # prompt a missing flag is not a pass.
        prompt_flag = (
            (data.get("userPromptAnalysis") or {}).get("attackDetected") if user_prompt else False
        )
        # A missing or non-boolean flag is not a pass.
        if len(flags) != len(documents) or not all(isinstance(f, bool) for f in flags):
            raise ScreenError("Prompt Shields answered without a flag for every document")
        if not isinstance(prompt_flag, bool):
            raise ScreenError("Prompt Shields answered without a flag for the prompt")
        return prompt_flag, [f is True for f in flags]

    def documents(self, texts: list[str], *, timeout: float) -> list[bool]:
        left = _deadline(timeout, self.clock)
        owners: list[int] = []
        parts: list[str] = []
        for index, text in enumerate(texts):
            # Nothing to screen in an empty text; it counts as shown.
            if not text.strip():
                continue
            for part in screen_pieces(text):
                owners.append(index)
                parts.append(part)
        flagged = [False] * len(texts)
        position = 0
        for batch in batches(parts):
            _, flags = self._call("", batch, left())
            for flag in flags:
                flagged[owners[position]] |= flag
                position += 1
        return flagged

    def prompt(self, text: str, *, timeout: float) -> bool:
        if utf16_units(text) > MAX_CHARACTERS:
            raise ScreenError(f"a prompt of {utf16_units(text)} UTF-16 units is over the limit")
        flag, _ = self._call(text, [], timeout)
        return flag


@dataclass(frozen=True)
class PiiHit:
    category: str
    # In code points from the start of the text sent (stringIndexType
    # UnicodeCodePoint), so they index a Python string directly.
    offset: int
    length: int
    confidence: float


class Pii(Protocol):
    calls: int
    records: int

    def __call__(self, texts: list[str], *, timeout: float) -> list[tuple[PiiHit, ...]]: ...


class PiiDetector:
    """Text PII detection: the hits in each text, offsets counted from the text's start."""

    def __init__(self, post: Post, clock: Callable[[], float] = time.monotonic) -> None:
        self.post = post
        self.clock = clock
        self.calls = 0
        self.records = 0

    def _call(self, documents: list[str], timeout: float) -> list[list[dict]]:
        body = {
            "kind": "PiiEntityRecognition",
            "parameters": {
                "modelVersion": PII_MODEL_VERSION,
                "stringIndexType": "UnicodeCodePoint",
            },
            "analysisInput": {
                "documents": [
                    {"id": str(i), "language": "en", "text": d} for i, d in enumerate(documents)
                ]
            },
        }
        try:
            data = self.post(
                f"/language/:analyze-text?api-version={PII_API_VERSION}", body, timeout=timeout
            )
        except ServiceError as error:
            raise PiiError(str(error)) from error
        self.calls += 1
        self.records += sum(math.ceil(len(d) / RECORD_CHARACTERS) for d in documents)
        try:
            results = data.get("results") or {}
            errors = results.get("errors") or []
            codes = sorted({str((e.get("error") or {}).get("code")) for e in errors})
            answered = {d.get("id"): d.get("entities") for d in results.get("documents") or []}
        except (AttributeError, TypeError) as error:
            raise PiiError("PII detection answered in an unknown shape") from error
        if errors:
            raise PiiError(f"documents not checked: {', '.join(codes)}")
        if set(answered) != {str(i) for i in range(len(documents))}:
            raise PiiError("PII detection answered for a different set of documents")
        out = []
        for i in range(len(documents)):
            entities = answered[str(i)]
            if not isinstance(entities, list):
                raise PiiError("PII detection answered without an entity list")
            out.append(entities)
        return out

    def __call__(self, texts: list[str], *, timeout: float) -> list[tuple[PiiHit, ...]]:
        left = _deadline(timeout, self.clock)
        # (text index, offset of the piece in the text, piece)
        parts: list[tuple[int, int, str]] = []
        for index, text in enumerate(texts):
            if not text.strip():
                continue
            offset = 0
            for part in pieces(text, PII_MAX_CHARACTERS):
                parts.append((index, offset, part))
                offset += len(part)
        hits: list[list[PiiHit]] = [[] for _ in texts]
        for start in range(0, len(parts), PII_MAX_DOCUMENTS):
            group = parts[start : start + PII_MAX_DOCUMENTS]
            answers = self._call([p for _, _, p in group], left())
            for (index, offset, piece), entities in zip(group, answers, strict=True):
                for e in entities:
                    try:
                        category, start, length = e["category"], e["offset"], e["length"]
                        confidence = float(e["confidenceScore"])
                    except (KeyError, TypeError, ValueError) as error:
                        raise PiiError(
                            "PII detection answered an entity without its fields"
                        ) from error
                    # A hit that does not fit its text cannot be masked: a pass
                    # would record a hit and leave the text as it was.
                    if not (isinstance(start, int) and isinstance(length, int)) or not (
                        start >= 0 and length > 0 and start + length <= len(piece)
                    ):
                        raise PiiError("PII detection answered a hit outside its text")
                    if category in NOT_PERSONAL:
                        continue
                    hits[index].append(PiiHit(category, offset + start, length, confidence))
        return [tuple(h) for h in hits]


def shield_client(settings: SafetySettings) -> PromptShield:
    return PromptShield(rest_post(settings.safety_endpoint))


def pii_client(settings: SafetySettings) -> PiiDetector:
    return PiiDetector(rest_post(settings.safety_endpoint))
