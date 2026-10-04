"""doctor.py is the doctor command's only shell entry, so it has to do three
things the separate scripts never had to: answer the interpreter question
itself, keep one broken report from hiding the others, and parse under an
interpreter too old to run anything else.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCTOR = ROOT / "scripts" / "doctor.py"
SCAFFOLD = ROOT / "scripts" / "scaffold.py"

sys.path.insert(0, str(ROOT / "scripts"))
import doctor  # noqa: E402


@pytest.fixture
def installed(tmp_path: Path) -> Path:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(SCAFFOLD), "--project-name", "Acme", "--slug", "acme",
         "--source-root", "src/acme", "--target", str(tmp_path)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return tmp_path


def test_a_fresh_install_reports_all_three_blocks(installed: Path) -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(DOCTOR), "--target", str(installed)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert out.startswith("interpreter: Python ")
    for block in ("[drift]", "[routing]", "[seats]"):
        assert block in out, out
    assert "match the shipped templates" in out


def test_a_repo_without_the_engine_says_so(tmp_path: Path) -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(DOCTOR), "--target", str(tmp_path)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 2
    assert "no .claude/" in proc.stdout


def test_an_old_interpreter_gets_a_line_and_exit_3(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
        installed: Path) -> None:
    """Exit 3 is what tells the command to try the next interpreter spelling."""
    monkeypatch.setattr(doctor, "MINIMUM", (99, 0))
    assert doctor.main(["--target", str(installed)]) == 3
    out = capsys.readouterr().out
    assert "older than 99.0" in out
    assert "[drift]" not in out


def test_one_failing_report_does_not_hide_the_others(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
        installed: Path) -> None:
    import drift

    def boom(_root: Path) -> list[str]:
        raise RuntimeError("synthetic")

    monkeypatch.setattr(drift, "report", boom)
    assert doctor.main(["--target", str(installed)]) == 0
    out = capsys.readouterr().out
    assert "drift: the check itself failed (RuntimeError: synthetic)" in out
    assert "[routing]" in out
    assert "[seats]" in out


def test_the_script_parses_without_modern_syntax() -> None:
    """An f-string or an annotation would make an old interpreter die with a
    SyntaxError before the version check could print its line."""
    tree = ast.parse(DOCTOR.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        assert not isinstance(node, ast.JoinedStr), f"f-string at line {node.lineno}"
        assert not isinstance(node, ast.AnnAssign), f"annotation at line {node.lineno}"
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert node.returns is None, f"return annotation on {node.name}"
            for arg in node.args.args + node.args.kwonlyargs:
                assert arg.annotation is None, f"annotation on {node.name}({arg.arg})"
        if isinstance(node, ast.ImportFrom):
            assert node.module != "__future__", "a __future__ import fails on 2.x"


def test_scaffold_refuses_an_old_interpreter(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
        tmp_path: Path) -> None:
    import scaffold

    monkeypatch.setattr(scaffold, "MINIMUM_PYTHON", (99, 0))
    code = scaffold.main(["--project-name", "Acme", "--slug", "acme",
                          "--target", str(tmp_path), "--dry-run"])
    assert code == 3
    assert "older than 99.0" in capsys.readouterr().out
    assert not (tmp_path / ".claude").exists()
