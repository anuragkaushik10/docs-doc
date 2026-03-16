from pathlib import Path

from docs_doc.analysis import analyze_repository, explain_path
from docs_doc.renderers.markdown import render_flow_markdown
from docs_doc.renderers.mermaid import render_mermaid_diagram

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_path(name: str) -> Path:
    return FIXTURES / name


def test_python_repo_analysis_detects_stack_and_entrypoints() -> None:
    analysis = analyze_repository(fixture_path("python_app"))

    assert "Python" in analysis.stack
    assert "Docker" in analysis.stack
    assert "GitHub Actions" in analysis.stack
    assert "FastAPI" in analysis.frameworks
    assert "app/main.py" in analysis.entrypoints
    assert "app" in analysis.major_folders
    assert any(edge.source == "app/main.py" and edge.target == "app" for edge in analysis.graph.edges)


def test_node_repo_analysis_detects_scripts_and_flow() -> None:
    analysis = analyze_repository(fixture_path("node_app"))

    assert "Node.js" in analysis.stack
    assert "Express" in analysis.frameworks
    assert "src/index.js" in analysis.entrypoints
    assert any(script.name == "start" for script in analysis.scripts)
    assert any("src/index.js" in line for line in analysis.probable_flow)


def test_monorepo_detects_workspace_roots() -> None:
    analysis = analyze_repository(fixture_path("monorepo"))

    assert analysis.monorepo_roots == ["packages/shared", "packages/web"]
    assert analysis.major_folders == ["packages/shared", "packages/web"]


def test_explain_file_reports_dependencies() -> None:
    explanation = explain_path(fixture_path("python_app"), Path("app/main.py"))

    assert explanation.target == "app/main.py"
    assert "app/routes.py" in explanation.depends_on
    assert "app/services.py" in explanation.depends_on
    assert explanation.read_next


def test_generic_repo_degrades_gracefully() -> None:
    analysis = analyze_repository(fixture_path("generic_repo"))

    assert analysis.stack == []
    assert analysis.entrypoints == []
    assert analysis.probable_flow


def test_flow_markdown_snapshot() -> None:
    analysis = analyze_repository(fixture_path("python_app"))
    expected = (Path(__file__).parent / "snapshots" / "python_flow.md").read_text(encoding="utf-8")

    assert render_flow_markdown(analysis) == expected


def test_mermaid_snapshot() -> None:
    analysis = analyze_repository(fixture_path("python_app"))
    expected = (Path(__file__).parent / "snapshots" / "python_flow.mmd").read_text(encoding="utf-8")

    assert render_mermaid_diagram(analysis.graph).strip() == expected.strip()
