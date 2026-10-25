"""Contract for hindcast.models: what ask_model sends and what it returns.

The real clients are replaced with fakes, so these tests make no network calls.
"""

from types import SimpleNamespace

import pytest

from hindcast import models
from hindcast.costs import TokenUsage

PNG = b"\x89PNG\r\n\x1a\nrest"
JPEG = b"\xff\xd8\xff\xe0rest"


class FakeResponses:
    def __init__(self, text="answer", cached_tokens: int | None = 20, status="completed"):
        details = None if cached_tokens is None else SimpleNamespace(cached_tokens=cached_tokens)
        incomplete = None if status == "completed" else SimpleNamespace(reason="max_output_tokens")
        self.calls = []
        self.response = SimpleNamespace(
            output_text=text,
            status=status,
            incomplete_details=incomplete,
            usage=SimpleNamespace(input_tokens=120, input_tokens_details=details, output_tokens=30),
        )

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def use_fake(monkeypatch, responses: FakeResponses) -> FakeResponses:
    monkeypatch.setattr(models, "openai_client", lambda: SimpleNamespace(responses=responses))
    return responses


@pytest.fixture
def fake(monkeypatch):
    return use_fake(monkeypatch, FakeResponses())


def test_ask_model_sends_system_as_instructions_and_user_as_input(fake):
    models.ask_model("gpt-6-luna", "Answer from the text.", "When did it happen?")

    [call] = fake.calls
    assert call["model"] == "gpt-6-luna"
    assert call["instructions"] == "Answer from the text."
    assert call["input"] == [
        {"role": "user", "content": [{"type": "input_text", "text": "When did it happen?"}]}
    ]


def test_ask_model_pins_reasoning_effort(fake):
    models.ask_model("gpt-6-luna", "system", "user")
    models.ask_model("gpt-6-luna", "system", "user", effort="low")

    assert [call["reasoning"] for call in fake.calls] == [{"effort": "medium"}, {"effort": "low"}]


def test_ask_model_sends_no_sampling_parameters(fake):
    models.ask_model("gpt-6-luna", "system", "user")

    [call] = fake.calls
    assert "temperature" not in call
    assert "top_p" not in call


@pytest.mark.parametrize(
    ("image", "data_url"),
    [
        (PNG, "data:image/png;base64,iVBORw0KGgpyZXN0"),
        (JPEG, "data:image/jpeg;base64,/9j/4HJlc3Q="),
    ],
)
def test_ask_model_attaches_image_as_data_url(fake, image, data_url):
    models.ask_model("gpt-6-luna", "system", "What does the figure show?", image=image)

    [call] = fake.calls
    assert call["input"] == [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "What does the figure show?"},
                {"type": "input_image", "image_url": data_url},
            ],
        }
    ]


def test_ask_model_rejects_unknown_image_type_before_calling(fake):
    with pytest.raises(ValueError):
        models.ask_model("gpt-6-luna", "system", "user", image=b"GIF89a....")

    assert fake.calls == []


def test_ask_model_returns_text_and_usage(fake):
    assert models.ask_model("gpt-6-luna", "system", "user") == (
        "answer",
        TokenUsage(input_tokens=120, cached_input_tokens=20, output_tokens=30),
    )


def test_ask_model_counts_missing_cache_details_as_zero(monkeypatch):
    use_fake(monkeypatch, FakeResponses(cached_tokens=None))

    _, usage = models.ask_model("gpt-6-luna", "system", "user")

    assert usage == TokenUsage(input_tokens=120, cached_input_tokens=0, output_tokens=30)


@pytest.mark.parametrize("text", ["", "  \n"])
def test_ask_model_rejects_empty_answer(monkeypatch, text):
    use_fake(monkeypatch, FakeResponses(text=text))

    with pytest.raises(RuntimeError):
        models.ask_model("gpt-6-luna", "system", "user")


def test_ask_model_rejects_an_incomplete_answer(monkeypatch):
    # A cut answer still has text; it must not pass as a complete result.
    use_fake(monkeypatch, FakeResponses(text="The ship left at", status="incomplete"))

    with pytest.raises(RuntimeError, match="max_output_tokens"):
        models.ask_model("gpt-6-luna", "system", "user")


def test_deployment_model_rejects_a_missing_version(monkeypatch):
    deployment = SimpleNamespace(model_name="gpt-6-luna", model_version=None)
    monkeypatch.setattr(
        models,
        "project_client",
        lambda: SimpleNamespace(deployments=SimpleNamespace(get=lambda name: deployment)),
    )

    with pytest.raises(RuntimeError, match="chat"):
        models.deployment_model("chat")


def test_deployment_model_reads_name_and_version(monkeypatch):
    asked = []

    def get(name):
        asked.append(name)
        return SimpleNamespace(model_name="gpt-6-luna", model_version="2026-09-22")

    monkeypatch.setattr(
        models, "project_client", lambda: SimpleNamespace(deployments=SimpleNamespace(get=get))
    )

    assert models.deployment_model("chat") == ("gpt-6-luna", "2026-09-22")
    assert asked == ["chat"]
