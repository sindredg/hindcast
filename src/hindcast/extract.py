"""Content Understanding analyzers for library pages, chart images, and answer keys.

The analyzer definitions are JSON files in analyzers/, so every extract traces
to a committed definition. ensure_analyzers refuses an analyzer in the service
that differs from its file; analyze runs the analyzer it is given without that
check (issue #15). replace_analyzer recreates an analyzer from its file; it
needs no delete, which the Content Understanding Contributor role lacks.

Calls go to the Foundry resource endpoint with a DefaultAzureCredential token.
They need a Content Understanding role at resource scope; the project-scope
role that covers model calls does not reach this endpoint.
"""

import functools
import json
from pathlib import Path

from azure.ai.contentunderstanding import ContentUnderstandingClient
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential

from hindcast.config import ExtractionSettings, load_settings

# Analyzer IDs cannot contain hyphens (the service refuses them), unlike file names.
ANALYZERS = {
    "hindcast_postmortem": "analyzers/postmortem.json",
    "hindcast_chart": "analyzers/chart.json",
    "hindcast_answer_key": "analyzers/answer-key.json",
}


class AnalyzerDiffers(ValueError):
    """The analyzer in the service is not the one its committed file defines."""


@functools.cache
def cu_client() -> ContentUnderstandingClient:
    return ContentUnderstandingClient(
        endpoint=load_settings(ExtractionSettings).cu_endpoint,
        credential=DefaultAzureCredential(),
    )


def definition(analyzer_id: str) -> dict:
    return json.loads(Path(ANALYZERS[analyzer_id]).read_text(encoding="utf-8"))


def _contains(served: object, wanted: object) -> bool:
    """True if everything in wanted is in served; the service adds defaults of its own."""
    if isinstance(wanted, dict):
        return isinstance(served, dict) and all(
            key in served and _contains(served[key], value) for key, value in wanted.items()
        )
    return served == wanted


def ensure_analyzers(client=None) -> list[str]:
    """Create the analyzers that do not exist yet; return the IDs created."""
    client = client or cu_client()
    created = []
    for analyzer_id, path in ANALYZERS.items():
        wanted = definition(analyzer_id)
        try:
            served = client.get_analyzer(analyzer_id).as_dict()
        except ResourceNotFoundError:
            client.begin_create_analyzer(analyzer_id, wanted).result()
            created.append(analyzer_id)
            continue
        if not _contains(served, wanted):
            raise AnalyzerDiffers(
                f"{analyzer_id}: the analyzer in the service differs from {path}; "
                "replace it with replace_analyzer"
            )
    return created


def replace_analyzer(analyzer_id: str, client=None) -> None:
    """Recreate one analyzer from its committed file, replacing the service's copy."""
    (client or cu_client()).begin_create_analyzer(
        analyzer_id, definition(analyzer_id), allow_replace=True
    ).result()


def analyze(analyzer_id: str, data: bytes, mime: str, client=None) -> dict:
    """Run one analyzer on one file; the raw result and what it used (pages, tokens)."""
    poller = (client or cu_client()).begin_analyze_binary(analyzer_id, data, content_type=mime)
    result = poller.result()
    usage = poller.usage
    return {"result": result.as_dict(), "usage": usage.as_dict() if usage else {}}
