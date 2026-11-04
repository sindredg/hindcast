"""Content Understanding analyzers for library pages, chart images, and answer keys.

The analyzer definitions are JSON files in analyzers/, so every extract traces
to a committed definition. ensure_analyzers and analyze refuse an analyzer in
the service that differs from its file, and analyze also refuses one whose
completion model is not the model of the extraction deployment. analyze
returns the deployment's model name and version with each result, since the
service's usage names the model but not its version. replace_analyzer
recreates an analyzer from its file; it needs no delete, which the Content
Understanding Contributor role lacks.

Calls go to the Foundry resource endpoint with a DefaultAzureCredential token.
They need a Content Understanding role at resource scope; the project-scope
role that covers model calls does not reach this endpoint.
"""

import functools
import json
from collections.abc import Callable
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


@functools.cache
def extraction_model() -> dict:
    """The extraction deployment's model name and version, read once per process."""
    from hindcast.models import deployment_model

    deployment = load_settings(ExtractionSettings).extraction_deployment
    name, version = deployment_model(deployment)
    return {"deployment": deployment, "name": name, "version": version}


@functools.cache
def check_analyzer(analyzer_id: str, client: ContentUnderstandingClient, model_name: str) -> None:
    """Refuse an analyzer that differs from its file or names another completion model.

    Cached, so each analyzer is read from the service once per process.
    """
    wanted = definition(analyzer_id)
    named = wanted["models"]["completion"]
    if named != model_name:
        raise AnalyzerDiffers(
            f"{analyzer_id}: {ANALYZERS[analyzer_id]} names {named}, "
            f"the extraction deployment runs {model_name}"
        )
    if not _contains(client.get_analyzer(analyzer_id).as_dict(), wanted):
        raise AnalyzerDiffers(
            f"{analyzer_id}: the analyzer in the service differs from {ANALYZERS[analyzer_id]}; "
            "replace it with replace_analyzer"
        )


@functools.cache
def check_defaults(client: ContentUnderstandingClient, model_name: str, deployment: str) -> None:
    """Refuse when the resource's defaults run the model on another deployment (#41).

    An analyzer names a model; the defaults map that name to the deployment
    that runs it. Without this check the recorded model could name a
    deployment that did not run. Cached: read once per process.
    """
    mapped = (client.get_defaults().model_deployments or {}).get(model_name)
    if mapped != deployment:
        raise AnalyzerDiffers(
            f"the Content Understanding defaults map {model_name} to {mapped}, "
            f"not to the extraction deployment {deployment}"
        )


def ensure_analyzers(client: ContentUnderstandingClient | None = None) -> list[str]:
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


def replace_analyzer(analyzer_id: str, client: ContentUnderstandingClient | None = None) -> None:
    """Recreate one analyzer from its committed file, replacing the service's copy."""
    (client or cu_client()).begin_create_analyzer(
        analyzer_id, definition(analyzer_id), allow_replace=True
    ).result()


def analyze(
    analyzer_id: str,
    data: bytes,
    mime: str,
    client: ContentUnderstandingClient | None = None,
    model: Callable[[], dict] = extraction_model,
) -> dict:
    """Run one checked analyzer on one file: the raw result, its usage, and the model."""
    client = client or cu_client()
    used = model()
    check_defaults(client, used["name"], used["deployment"])
    check_analyzer(analyzer_id, client, used["name"])
    poller = client.begin_analyze_binary(analyzer_id, data, content_type=mime)
    result = poller.result()
    usage = poller.usage
    return {"result": result.as_dict(), "usage": usage.as_dict() if usage else {}, "model": used}
