"""The template's settings that a result depends on, checked in its source (decision 0028)."""

import re
from pathlib import Path

INFRA = Path(__file__).resolve().parents[1] / "infra"
FOUNDRY = INFRA / "modules/foundry.bicep"

# The deployments every result names (decisions 0012, 0014, 0018).
PINNED = {
    "gpt-6-luna": "2026-09-22",
    "gpt-6.1-sol": "2026-09-29",
    "gpt-5.4-mini": "2026-03-17",
    "text-embedding-3-large": "1",
}


def _deployments(text: str) -> dict[str, str]:
    pattern = r"\{ name: '([^']+)', format: 'OpenAI', version: '([^']+)' \}"
    return dict(re.findall(pattern, text))


def test_every_deployment_is_pinned():
    text = FOUNDRY.read_text(encoding="utf-8")
    assert _deployments(text) == PINNED
    upgrades = re.findall(r"versionUpgradeOption: '([^']+)'", text)
    assert upgrades == ["NoAutoUpgrade"]


def test_no_service_takes_a_key():
    sources = {p.name: p.read_text(encoding="utf-8") for p in (INFRA / "modules").glob("*.bicep")}
    assert "disableLocalAuth: true" in sources["foundry.bicep"]
    assert "disableLocalAuth: true" in sources["search.bicep"]
    assert "features: { disableLocalAuth: true }" in sources["monitoring.bicep"]
    assert "allowSharedKeyAccess: false" in sources["storage.bicep"]
    assert "allowBlobPublicAccess: false" in sources["storage.bicep"]
