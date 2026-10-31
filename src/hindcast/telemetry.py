"""Traces to Application Insights, configured once per process.

The connection string is configuration, not a credential: it can write
telemetry and read nothing (decision 0011). Without it, every call here is a
no-op, so tests and local runs need no exporter.
"""

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.trace import Span

CONNECTION_VAR = "APPLICATIONINSIGHTS_CONNECTION_STRING"
# Read by the OpenTelemetry GenAI instrumentations: "true" records prompt and
# completion text in spans. Decision 0011 keeps it off outside development.
CONTENT_RECORDING_VAR = "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"
# Application Insights shows service.name as the role name. Without it, the
# page's spans arrive as "unknown_service:python".
SERVICE = "hindcast-web"

# Streamlit re-runs the page script on every interaction. A second
# configure_azure_monitor() would attach a second exporter, so the module
# remembers that it already ran.
_configured = False


def configure(env: Mapping[str, str] = os.environ) -> bool:
    """Configure the Azure Monitor exporter once. True when this call did it."""
    global _configured
    connection = env.get(CONNECTION_VAR, "").strip()
    if _configured or not connection:
        return False
    development = env.get("HINDCAST_ENV") == "development"
    os.environ[CONTENT_RECORDING_VAR] = "true" if development else "false"
    configure_azure_monitor(
        connection_string=connection,
        enable_live_metrics=False,
        resource=Resource.create({SERVICE_NAME: SERVICE}),
    )
    _configured = True
    return True


@contextmanager
def span(name: str, **attributes: str) -> Iterator[Span]:
    """Open a span with string attributes; a non-recording span when nothing is configured."""
    tracer = trace.get_tracer("hindcast")
    with tracer.start_as_current_span(name, attributes=attributes) as current:
        yield current
