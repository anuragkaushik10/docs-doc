from __future__ import annotations

from pathlib import Path

import typer

from docs_doc.analysis import analyze_repository, explain_path
from docs_doc.renderers import (
    render_explanation,
    render_flow_markdown,
    render_flow_terminal,
    render_overview,
    render_overview_markdown,
    render_setup,
)

app = typer.Typer(help="Understand a repository faster.")


def _validate_repo_path(path: Path) -> Path:
    repo_path = path.resolve()
    if not repo_path.exists():
        typer.echo(f"Path does not exist: {repo_path}", err=True)
        raise typer.Exit(code=1)
    if not repo_path.is_dir():
        typer.echo(f"Path is not a directory: {repo_path}", err=True)
        raise typer.Exit(code=1)
    return repo_path


@app.command()
def overview(
    path: Path = typer.Argument(Path("."), exists=False, file_okay=False, dir_okay=True, readable=True),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write a markdown overview to this path."),
) -> None:
    """Scan a repository and print a quick overview."""
    repo_path = _validate_repo_path(path)
    analysis = analyze_repository(repo_path)
    typer.echo(render_overview(analysis))
    if output is not None:
        output_path = output if output.is_absolute() else Path.cwd() / output
        output_path.write_text(render_overview_markdown(analysis), encoding="utf-8")
        typer.echo(f"Wrote overview markdown to {output_path}")


@app.command()
def setup(
    path: Path = typer.Argument(Path("."), exists=False, file_okay=False, dir_okay=True, readable=True),
) -> None:
    """Print setup and runtime hints for a repository."""
    repo_path = _validate_repo_path(path)
    analysis = analyze_repository(repo_path)
    typer.echo(render_setup(analysis.setup, analysis.repo_name))


@app.command()
def explain(
    target: Path = typer.Argument(..., exists=False, readable=True),
    root: Path = typer.Option(Path("."), "--root", help="Repository root for relative target resolution."),
) -> None:
    """Explain a file or folder inside a repository."""
    repo_root = _validate_repo_path(root)
    try:
        explanation = explain_path(repo_root, target)
    except FileNotFoundError:
        typer.echo(f"Target does not exist inside the repository: {target}", err=True)
        raise typer.Exit(code=1)
    typer.echo(render_explanation(explanation))


@app.command()
def flow(
    path: Path = typer.Argument(Path("."), exists=False, file_okay=False, dir_okay=True, readable=True),
    output: Path = typer.Option(Path("REPO_FLOW.md"), "--output", "-o", help="Write the flow document to this path."),
    no_diagram: bool = typer.Option(False, "--no-diagram", help="Skip the Mermaid diagram in the markdown output."),
) -> None:
    """Generate a repo flow summary and markdown document."""
    repo_path = _validate_repo_path(path)
    analysis = analyze_repository(repo_path)
    output_path = output if output.is_absolute() else Path.cwd() / output
    output_path.write_text(render_flow_markdown(analysis, include_diagram=not no_diagram), encoding="utf-8")
    typer.echo(render_flow_terminal(analysis, str(output_path)))


if __name__ == "__main__":
    app()
