from pathlib import Path

from typer.testing import CliRunner

from docs_doc.cli import app

RUNNER = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


def test_overview_command() -> None:
    result = RUNNER.invoke(app, ["overview", str(FIXTURES / "node_app")])

    assert result.exit_code == 0
    assert "Repository: node_app" in result.stdout
    assert "src/index.js" in result.stdout


def test_setup_command() -> None:
    result = RUNNER.invoke(app, ["setup", str(FIXTURES / "python_app")])

    assert result.exit_code == 0
    assert "python -m pip install -e" in result.stdout
    assert "python app/main.py" in result.stdout


def test_explain_command() -> None:
    result = RUNNER.invoke(
        app,
        ["explain", "app/main.py", "--root", str(FIXTURES / "python_app")],
    )

    assert result.exit_code == 0
    assert "Explain: app/main.py" in result.stdout
    assert "app/routes.py" in result.stdout


def test_flow_command_writes_markdown(tmp_path: Path) -> None:
    output_path = tmp_path / "REPO_FLOW.md"
    result = RUNNER.invoke(
        app,
        ["flow", str(FIXTURES / "python_app"), "--output", str(output_path)],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    written = output_path.read_text(encoding="utf-8")
    assert "# Repo Flow" in written
    assert "```mermaid" in written


def test_invalid_path_returns_error() -> None:
    result = RUNNER.invoke(app, ["overview", "missing-repo"])

    assert result.exit_code == 1
    assert "Path does not exist" in result.stderr
