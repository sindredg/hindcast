"""Telemetry is configured once per process, and only with a connection string."""

import pytest

from hindcast import telemetry

CONNECTION = "InstrumentationKey=00000000-0000-0000-0000-000000000000"


@pytest.fixture
def recorded(monkeypatch):
    monkeypatch.setattr(telemetry, "_configured", False)
    calls: list[dict] = []
    monkeypatch.setattr(telemetry, "configure_azure_monitor", lambda **kw: calls.append(kw))
    return calls


def test_configure_without_connection_string_is_noop(recorded):
    assert telemetry.configure({}) is False
    assert recorded == []


def test_configure_once_per_process(recorded):
    env = {"APPLICATIONINSIGHTS_CONNECTION_STRING": CONNECTION}

    assert telemetry.configure(env) is True
    assert telemetry.configure(env) is False

    assert len(recorded) == 1
    assert recorded[0]["connection_string"] == CONNECTION
    assert recorded[0]["enable_live_metrics"] is False


@pytest.mark.parametrize(
    ("hindcast_env", "expected"),
    [("development", "true"), ("production", "false"), (None, "false")],
)
def test_content_recording_only_in_development(recorded, monkeypatch, hindcast_env, expected):
    monkeypatch.delenv(telemetry.CONTENT_RECORDING_VAR, raising=False)
    env = {"APPLICATIONINSIGHTS_CONNECTION_STRING": CONNECTION}
    if hindcast_env is not None:
        env["HINDCAST_ENV"] = hindcast_env

    assert telemetry.configure(env) is True

    assert telemetry.os.environ[telemetry.CONTENT_RECORDING_VAR] == expected


def test_span_yields_a_span_with_attributes():
    with telemetry.span("page_view", case_id="cloudflare-2026-02-20") as current:
        assert current is not None
        # Without an exporter the SDK hands back a non-recording span; the
        # call shape is what this test pins.
        assert hasattr(current, "set_attribute")
