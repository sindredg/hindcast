import json
from pathlib import Path

import pytest
from azure.ai.contentunderstanding import models
from azure.core.exceptions import ResourceNotFoundError

from hindcast.extract import ANALYZERS, AnalyzerDiffers, analyze, definition, ensure_analyzers


def test_every_analyzer_file_is_valid_json_with_its_id():
    assert sorted(ANALYZERS) == ["hindcast_answer_key", "hindcast_chart", "hindcast_postmortem"]
    for analyzer_id, path in ANALYZERS.items():
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data["analyzerId"] == analyzer_id
        # gpt-5-mini is a deployed model on the GA API's supported list. The
        # document base also needs an embedding model; named here, the base's
        # own alias is never resolved.
        models = {"completion": "gpt-5-mini"}
        if data["baseAnalyzerId"] == "prebuilt-document":
            models["embedding"] = "text-embedding-3-large"
        assert data["models"] == models, analyzer_id
        assert data["fieldSchema"]["fields"], analyzer_id


def test_answer_key_analyzer_allows_only_the_defined_attack_values():
    fields = definition("hindcast_answer_key")["fieldSchema"]["fields"]

    assert fields["attack"]["enum"] == ["attack", "not an attack"]
    assert fields["attack_basis"]["enum"] == ["stated", "implied", "not stated"]
    assert sorted(fields) == [
        "attack",
        "attack_basis",
        "contributing_factors",
        "fixes",
        "root_cause",
        "timeline",
    ]
    assert sorted(fields["timeline"]["items"]["properties"]) == ["event", "time"]


def rest_names(model: type) -> set[str]:
    # The SDK fills this map when a model is first built; the pin keeps it stable.
    model({})
    return {field._rest_name for field in model._attr_to_rest_field.values()}


def unknown_keys(field: dict, where: str) -> list[str]:
    unknown = [f"{where}.{key}" for key in field.keys() - rest_names(models.ContentFieldDefinition)]
    for name, sub in field.get("properties", {}).items():
        unknown += unknown_keys(sub, f"{where}.{name}")
    if "items" in field:
        unknown += unknown_keys(field["items"], f"{where}.items")
    return unknown


def test_analyzer_files_use_only_keys_the_api_defines():
    # A misspelt key would be dropped by the service without an error.
    for analyzer_id in ANALYZERS:
        data = definition(analyzer_id)
        unknown = sorted(data.keys() - rest_names(models.ContentAnalyzer))
        unknown += sorted(data.get("config", {}).keys() - rest_names(models.ContentAnalyzerConfig))
        unknown += sorted(data["fieldSchema"].keys() - rest_names(models.ContentFieldSchema))
        for name, field in data["fieldSchema"]["fields"].items():
            unknown += unknown_keys(field, name)
        assert unknown == [], analyzer_id


class FakeAnalyzer:
    def __init__(self, data: dict):
        self.data = data

    def as_dict(self) -> dict:
        return self.data


class FakePoller:
    def __init__(self, value=None, usage=None):
        self.value, self.usage = value, usage

    def result(self):
        return self.value


class FakeClient:
    """Holds analyzers by ID, as the service returns them (with defaults filled in)."""

    def __init__(self, existing: dict[str, dict]):
        self.existing = existing
        self.created: list[str] = []

    def get_analyzer(self, analyzer_id: str) -> FakeAnalyzer:
        if analyzer_id not in self.existing:
            raise ResourceNotFoundError("not found")
        return FakeAnalyzer(self.existing[analyzer_id])

    def begin_create_analyzer(self, analyzer_id: str, resource: dict) -> FakePoller:
        self.created.append(analyzer_id)
        self.existing[analyzer_id] = resource
        return FakePoller()


def as_served(analyzer_id: str) -> dict:
    data = definition(analyzer_id)
    return data | {"status": "ready", "config": data.get("config", {}) | {"enableOcr": True}}


def test_ensure_analyzers_creates_only_missing_ones():
    client = FakeClient({"hindcast_postmortem": as_served("hindcast_postmortem")})

    assert ensure_analyzers(client) == ["hindcast_chart", "hindcast_answer_key"]
    assert client.created == ["hindcast_chart", "hindcast_answer_key"]
    assert ensure_analyzers(client) == []


def test_an_analyzer_that_differs_from_its_file_is_refused():
    served = as_served("hindcast_answer_key")
    served["fieldSchema"]["fields"]["attack"] = served["fieldSchema"]["fields"]["attack"] | {
        "enum": ["attack", "not an attack", "cannot tell"]
    }
    client = FakeClient({analyzer_id: as_served(analyzer_id) for analyzer_id in ANALYZERS})
    client.existing["hindcast_answer_key"] = served

    with pytest.raises(AnalyzerDiffers, match="hindcast_answer_key"):
        ensure_analyzers(client)
    assert client.created == []


def test_analyze_returns_the_result_and_its_usage():
    class Client:
        def begin_analyze_binary(self, analyzer_id, binary_input, *, content_type):
            self.call = (analyzer_id, binary_input, content_type)
            return FakePoller(FakeAnalyzer({"contents": []}), FakeAnalyzer({"tokens": {"a": 1}}))

    client = Client()

    out = analyze("hindcast_chart", b"\x89PNG", "image/png", client=client)

    assert client.call == ("hindcast_chart", b"\x89PNG", "image/png")
    assert out == {"result": {"contents": []}, "usage": {"tokens": {"a": 1}}}
