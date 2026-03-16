from __future__ import annotations

from docs_doc.analysis.models import PathExplanation, RepositoryAnalysis, SetupHints


def render_overview(analysis: RepositoryAnalysis) -> str:
    sections = [
        f"Repository: {analysis.repo_name}",
        "",
        analysis.summary,
        "",
        _section("Stack", analysis.stack or ["Unknown"]),
        _section("Package Managers", analysis.package_managers or ["None detected"]),
        _section("Framework Clues", analysis.frameworks or ["None detected"]),
        _section("Important Files", analysis.important_files or ["None detected"]),
        _section("Major Folders", analysis.major_folders or ["None detected"]),
        _section("Entrypoints", _limit_items(analysis.entrypoints) or ["None detected"]),
        _section(
            "Scripts",
            _limit_items([f"{script.name} ({script.source}) -> {script.command}" for script in analysis.scripts])
            or ["None detected"],
        ),
        _section("Probable Flow", analysis.probable_flow or ["No clear flow could be inferred."]),
    ]
    return "\n".join(sections).strip() + "\n"


def render_setup(setup: SetupHints, repo_name: str) -> str:
    sections = [
        f"Setup Guide: {repo_name}",
        "",
        _section("Install", setup.install or ["No reliable install command detected"]),
        _section("Run", setup.run or ["No reliable run command detected"]),
        _section("Test", setup.test or ["No reliable test command detected"]),
        _section("Env Files", setup.env_files or ["None detected"]),
        _section("Config Files", setup.config_files or ["None detected"]),
        _section("Docker Files", setup.docker_files or ["None detected"]),
        _section("CI Files", setup.ci_files or ["None detected"]),
        _section("Notes", setup.notes or ["None"]),
        _section("Missing Signals", setup.missing_signals or ["None"]),
    ]
    return "\n".join(sections).strip() + "\n"


def render_explanation(explanation: PathExplanation) -> str:
    sections = [
        f"Explain: {explanation.target}",
        "",
        explanation.purpose,
        "",
        _section("Depends On", explanation.depends_on or ["No internal dependencies detected"]),
        _section("Used By", explanation.used_by or ["No internal dependents detected"]),
        _section("Key Files", explanation.key_files or ["No nearby key files detected"]),
        _section("Read Next", explanation.read_next or ["No follow-up suggestions available"]),
        _section("Notes", explanation.notes or ["None"]),
    ]
    return "\n".join(sections).strip() + "\n"


def render_flow_terminal(analysis: RepositoryAnalysis, output_path: str) -> str:
    sections = [
        f"Flow Document: {analysis.repo_name}",
        "",
        analysis.summary,
        "",
        _section("Entrypoints", _limit_items(analysis.entrypoints) or ["None detected"]),
        _section("Major Modules", analysis.major_folders or ["None detected"]),
        _section("Dependency Flow", analysis.probable_flow or ["No clear flow could be inferred."]),
        f"Markdown output: {output_path}",
    ]
    return "\n".join(sections).strip() + "\n"


def _section(title: str, items: list[str]) -> str:
    lines = [f"{title}:"]
    lines.extend(f"- {item}" for item in items)
    return "\n".join(lines)


def _limit_items(items: list[str], limit: int = 8) -> list[str]:
    if len(items) <= limit:
        return items
    remaining = len(items) - limit
    return [*items[:limit], f"... and {remaining} more"]
