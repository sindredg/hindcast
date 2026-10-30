"""The investigator never reaches the answer keys or a postmortem, in code."""

import ast
import builtins
import io
from pathlib import Path
from typing import Any

import pytest

from hindcast.cases import load_cases
from test_investigate import FakeClient, call, final, response, stub_command

SRC = Path("src")
INVESTIGATOR = ("hindcast.investigate", "hindcast.tools", "hindcast.result", "hindcast.agent")


def _module_path(module: str) -> Path:
    base = SRC / module.replace(".", "/")
    return base / "__init__.py" if base.is_dir() else base.with_suffix(".py")


def _is_module(name: str) -> bool:
    return name.startswith("hindcast") and _module_path(name).is_file()


def _hindcast_imports(module: str) -> set[str]:
    path = _module_path(module)
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text("utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            # "from hindcast import keys" names the module in the alias.
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return {n for n in names if _is_module(n)}


def reachable(modules: tuple[str, ...]) -> set[str]:
    """Every hindcast module the investigator imports, directly or through others."""
    seen: set[str] = set()
    todo = list(modules)
    while todo:
        module = todo.pop()
        if module not in seen:
            seen.add(module)
            todo.extend(_hindcast_imports(module))
    return seen


def test_reachable_finds_a_transitive_import() -> None:
    # hindcast.agent imports hindcast.evaluation.prior, which imports hindcast.cases.
    assert "hindcast.cases" in reachable(("hindcast.agent",))


def test_investigator_modules_do_not_import_keys() -> None:
    assert "hindcast.keys" not in reachable(INVESTIGATOR)


def test_investigator_opens_nothing_under_eval_keys_or_a_postmortem(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    postmortems = {
        source.filename
        for case in load_cases().values()
        for source in case.sources
        if source.kind == "postmortem"
    }
    assert postmortems
    client = FakeClient(response(call()), final())
    stub_command(monkeypatch, tmp_path, client)

    opened: list[Path] = []
    real_open = io.open

    def recording_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        opened.append(Path(str(file)).resolve())
        return real_open(file, *args, **kwargs)

    # Path.open and the open() builtin both go through io.open.
    monkeypatch.setattr(io, "open", recording_open)
    monkeypatch.setattr(builtins, "open", recording_open)
    from hindcast.investigate import main

    main(["dev", "--out", str(tmp_path / "out")])

    keys = (Path("eval") / "keys").resolve()
    assert opened, "the recorder saw no file opened"
    assert not [p for p in opened if p.is_relative_to(keys)]
    assert not [p for p in opened if p.name in postmortems]
