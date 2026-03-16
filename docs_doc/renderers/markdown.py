from __future__ import annotations

from docs_doc.analysis.models import PathExplanation, RepositoryAnalysis
from docs_doc.renderers.mermaid import render_mermaid_diagram


def render_overview_markdown(analysis: RepositoryAnalysis) -> str:
    sections = [
        f"# {analysis.repo_name} Overview",
        "",
        analysis.summary,
        "",
        "## Stack",
        _markdown_list(analysis.stack or ["Unknown"]),
        "",
        "## Framework Clues",
        _markdown_list(analysis.frameworks or ["None detected"]),
        "",
        "## Important Files",
        _markdown_list(analysis.important_files or ["None detected"]),
        "",
        "## Major Folders",
        _markdown_list(analysis.major_folders or ["None detected"]),
        "",
        "## Entrypoints",
        _markdown_list(_limit_items(analysis.entrypoints) or ["None detected"]),
        "",
        "## Scripts",
        _markdown_list(
            _limit_items([f"`{script.name}` via `{script.source}`: `{script.command}`" for script in analysis.scripts])
            or ["None detected"]
        ),
        "",
        "## Probable Flow",
        _markdown_list(analysis.probable_flow or ["No clear flow could be inferred."]),
    ]
    return "\n".join(sections).rstrip() + "\n"


def render_flow_markdown(analysis: RepositoryAnalysis, include_diagram: bool = True) -> str:
    sections = [
        "# Repo Flow",
        "",
        analysis.summary,
        "",
        "## Detected Entrypoints",
        _markdown_list(_limit_items(analysis.entrypoints) or ["None detected"]),
        "",
        "## Major Modules",
        _markdown_list(analysis.major_folders or ["None detected"]),
        "",
        "## Dependency Flow",
        _markdown_list(analysis.probable_flow or ["No clear flow could be inferred."]),
        "",
        "## Start Here",
        _markdown_list(_start_here(analysis)),
    ]
    if include_diagram:
        sections.extend(
            [
                "",
                "## Diagram",
                "",
                "```mermaid",
                render_mermaid_diagram(analysis.graph),
                "```",
            ]
        )
    return "\n".join(sections).rstrip() + "\n"


def render_explanation_markdown(explanation: PathExplanation) -> str:
    sections = [
        f"# Explain `{explanation.target}`",
        "",
        explanation.purpose,
        "",
        "## Depends On",
        _markdown_list(explanation.depends_on or ["No internal dependencies detected"]),
        "",
        "## Used By",
        _markdown_list(explanation.used_by or ["No internal dependents detected"]),
        "",
        "## Key Files",
        _markdown_list(explanation.key_files or ["No nearby key files detected"]),
        "",
        "## Read Next",
        _markdown_list(explanation.read_next or ["No follow-up suggestions available"]),
    ]
    return "\n".join(sections).rstrip() + "\n"


def _markdown_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _start_here(analysis: RepositoryAnalysis) -> list[str]:
    suggestions = []
    suggestions.extend(analysis.entrypoints[:2])
    suggestions.extend(analysis.important_files[:3])
    if analysis.setup.env_files:
        suggestions.extend(analysis.setup.env_files[:1])
    deduped: list[str] = []
    for item in suggestions:
        if item not in deduped:
            deduped.append(item)
    return deduped or ["README.md"]


def _limit_items(items: list[str], limit: int = 8) -> list[str]:
    if len(items) <= limit:
        return items
    remaining = len(items) - limit
    return [*items[:limit], f"... and {remaining} more"]
