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


def test_nested_fixture_manifests_do_not_pollute_root_analysis(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\nversion = '0.1.0'\n", encoding="utf-8")
    (tmp_path / "docs_doc").mkdir()
    (tmp_path / "docs_doc" / "__main__.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "tests" / "fixtures" / "demo").mkdir(parents=True)
    (tmp_path / "tests" / "fixtures" / "demo" / "package.json").write_text('{"name":"demo-node"}\n', encoding="utf-8")

    analysis = analyze_repository(tmp_path)

    assert analysis.stack == ["Python"]
    assert "package.json" not in analysis.important_files


def test_entrypoint_detection_requires_real_main_guard(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\nversion = '0.1.0'\n", encoding="utf-8")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "runner.py").write_text(
        "def main():\n    return 1\n\nif __name__ == \"__main__\":\n    main()\n",
        encoding="utf-8",
    )
    (tmp_path / "app" / "notes.py").write_text(
        "TEXT = '__main__ is only mentioned here'\n",
        encoding="utf-8",
    )
    (tmp_path / "REPO_FLOW.md").write_text("# generated\n", encoding="utf-8")

    analysis = analyze_repository(tmp_path)

    assert "app/runner.py" in analysis.entrypoints
    assert "app/notes.py" not in analysis.entrypoints
    assert "REPO_FLOW.md" not in analysis.important_files


def test_flow_markdown_snapshot() -> None:
    analysis = analyze_repository(fixture_path("python_app"))
    expected = (Path(__file__).parent / "snapshots" / "python_flow.md").read_text(encoding="utf-8")

    assert render_flow_markdown(analysis) == expected


def test_mermaid_snapshot() -> None:
    analysis = analyze_repository(fixture_path("python_app"))
    expected = (Path(__file__).parent / "snapshots" / "python_flow.mmd").read_text(encoding="utf-8")

    assert render_mermaid_diagram(analysis.graph).strip() == expected.strip()
