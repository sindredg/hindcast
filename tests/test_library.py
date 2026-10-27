import re
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from hindcast.cases import load_cases
from hindcast.evidence import cut

LIBRARY = Path("data/library.yaml")
TAG = re.compile(r"(product|symptom|scale): \S.*")


def symptoms() -> dict[str, list[dict]]:
    return YAML(typ="safe", pure=True).load(LIBRARY)["symptoms"]


def test_every_case_has_tagged_symptoms():
    cases = load_cases()
    tagged = symptoms()

    assert sorted(tagged) == sorted(cases)
    for case_id, tags in tagged.items():
        assert tags, case_id
        for tag in tags:
            assert sorted(tag) == ["quote", "tag", "update_id"], (case_id, tag)
            assert TAG.fullmatch(tag["tag"]), (case_id, tag["tag"])
            assert tag["quote"].strip(), (case_id, tag["tag"])
            assert tag["update_id"].startswith(f"{case_id}/u"), (case_id, tag["update_id"])


def test_symptom_quotes_appear_in_their_update():
    # Picks rest on what the live updates showed, so every tag has to quote the
    # cut evidence word for word, never the postmortem.
    checked = 0
    for case in load_cases().values():
        status = next(s for s in case.sources if s.kind == "status-updates")
        path = Path("data/sources") / case.case_id / status.filename
        if not path.is_file():
            continue
        updates = {u.update_id: u.text for u in cut(case, path.read_bytes()).updates}
        for tag in symptoms()[case.case_id]:
            # A bool, so a failure names the tag without printing the update.
            text = updates.get(tag["update_id"])
            found = text is not None and tag["quote"] in text
            assert found, (tag["update_id"], tag["quote"])
            checked += 1
    if not checked:
        pytest.skip("no local status snapshots under data/sources/")
