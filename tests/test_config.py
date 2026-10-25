import pytest

from hindcast.config import ConfigError, Settings, load_settings

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


def test_load_settings_reads_all_fields():
    settings = load_settings(FULL_ENV)

    assert settings == Settings(
        project_endpoint="https://example.services.ai.azure.com/api/projects/hindcast",
        search_endpoint="https://example.search.windows.net",
        search_index="hindcast-evidence",
        storage_url="https://example.blob.core.windows.net",
        chat_deployment="chat",
        judge_deployment="judge",
        compare_deployment="compare",
        embedding_deployment="embedding",
        embedding_dimensions=3072,
        cu_endpoint="https://example.services.ai.azure.com/",
    )


def test_embedding_dimensions_defaults_to_1024():
    env = {k: v for k, v in FULL_ENV.items() if k != "HINDCAST_EMBEDDING_DIMENSIONS"}

    assert load_settings(env).embedding_dimensions == 1024


def test_missing_vars_named_in_error():
    env = {
        k: v
        for k, v in FULL_ENV.items()
        if k not in ("HINDCAST_SEARCH_INDEX", "HINDCAST_CU_ENDPOINT")
    }

    with pytest.raises(ConfigError) as excinfo:
        load_settings(env)

    message = str(excinfo.value)
    assert "HINDCAST_SEARCH_INDEX" in message
    assert "HINDCAST_CU_ENDPOINT" in message


def test_empty_value_counts_as_missing():
    env = FULL_ENV | {"HINDCAST_CHAT_DEPLOYMENT": "  "}

    with pytest.raises(ConfigError, match="HINDCAST_CHAT_DEPLOYMENT"):
        load_settings(env)


@pytest.mark.parametrize("value", ["abc", "0", "-5"])
def test_bad_embedding_dimensions_rejected(value):
    env = FULL_ENV | {"HINDCAST_EMBEDDING_DIMENSIONS": value}

    with pytest.raises(ConfigError, match="HINDCAST_EMBEDDING_DIMENSIONS"):
        load_settings(env)


def test_settings_are_frozen():
    settings = load_settings(FULL_ENV)

    with pytest.raises(AttributeError):
        settings.chat_deployment = "other"
