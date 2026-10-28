import pytest

from hindcast.config import (
    ConfigError,
    ExtractionSettings,
    ModelSettings,
    SearchSettings,
    StorageSettings,
    load_settings,
)

FULL_ENV = {
    "HINDCAST_PROJECT_ENDPOINT": "https://example.services.ai.azure.com/api/projects/hindcast",
    "HINDCAST_SEARCH_ENDPOINT": "https://example.search.windows.net",
    "HINDCAST_SEARCH_INDEX": "hindcast-evidence",
    "HINDCAST_STORAGE_URL": "https://example.blob.core.windows.net",
    "HINDCAST_CHAT_DEPLOYMENT": "chat",
    "HINDCAST_JUDGE_DEPLOYMENT": "judge",
    "HINDCAST_COMPARE_DEPLOYMENT": "compare",
    "HINDCAST_EMBEDDING_DEPLOYMENT": "embedding",
    "HINDCAST_EMBEDDING_DIMENSIONS": "3072",
    "HINDCAST_CU_ENDPOINT": "https://example.services.ai.azure.com/",
}

# The .env the foundations runbook writes: search and embedding stay empty
# until milestone 3.
RUNBOOK_ENV = FULL_ENV | {
    "HINDCAST_SEARCH_ENDPOINT": "",
    "HINDCAST_SEARCH_INDEX": "",
    "HINDCAST_EMBEDDING_DEPLOYMENT": "",
    "HINDCAST_EMBEDDING_DIMENSIONS": "",
}


def test_runbook_env_loads_what_milestone_2_needs():
    assert load_settings(StorageSettings, RUNBOOK_ENV) == StorageSettings(
        storage_url="https://example.blob.core.windows.net"
    )
    assert load_settings(ModelSettings, RUNBOOK_ENV) == ModelSettings(
        project_endpoint="https://example.services.ai.azure.com/api/projects/hindcast",
        chat_deployment="chat",
        compare_deployment="compare",
        judge_deployment="judge",
    )
    assert load_settings(ExtractionSettings, RUNBOOK_ENV) == ExtractionSettings(
        cu_endpoint="https://example.services.ai.azure.com/"
    )


def test_search_settings_name_every_missing_variable():
    with pytest.raises(ConfigError) as excinfo:
        load_settings(SearchSettings, RUNBOOK_ENV)

    message = str(excinfo.value)
    for name in (
        "HINDCAST_SEARCH_ENDPOINT",
        "HINDCAST_SEARCH_INDEX",
        "HINDCAST_EMBEDDING_DEPLOYMENT",
    ):
        assert name in message


def test_search_settings_read_all_fields():
    assert load_settings(SearchSettings, FULL_ENV) == SearchSettings(
        search_endpoint="https://example.search.windows.net",
        search_index="hindcast-evidence",
        embedding_deployment="embedding",
        embedding_dimensions=3072,
    )


def test_embedding_dimensions_defaults_to_1024():
    env = {k: v for k, v in FULL_ENV.items() if k != "HINDCAST_EMBEDDING_DIMENSIONS"}

    assert load_settings(SearchSettings, env).embedding_dimensions == 1024


def test_empty_value_counts_as_missing():
    env = FULL_ENV | {"HINDCAST_CHAT_DEPLOYMENT": "  "}

    with pytest.raises(ConfigError, match="HINDCAST_CHAT_DEPLOYMENT"):
        load_settings(ModelSettings, env)


@pytest.mark.parametrize("value", ["abc", "0", "-5"])
def test_bad_embedding_dimensions_rejected(value):
    env = FULL_ENV | {"HINDCAST_EMBEDDING_DIMENSIONS": value}

    with pytest.raises(ConfigError, match="HINDCAST_EMBEDDING_DIMENSIONS"):
        load_settings(SearchSettings, env)


def test_settings_are_frozen():
    settings = load_settings(ModelSettings, FULL_ENV)

    with pytest.raises(AttributeError):
        settings.chat_deployment = "other"  # pyright: ignore[reportAttributeAccessIssue]
