# docs-doc

`docs-doc` is a CLI for understanding unfamiliar repositories faster.

It scans a repo, detects the likely stack and entrypoints, builds a high-level
dependency graph, and turns that into:

- terminal-friendly summaries
- setup guidance
- targeted explanations for files and folders
- a `REPO_FLOW.md` document with a Mermaid diagram

## Commands

```bash
docs-doc overview .
docs-doc setup .
docs-doc explain path/to/file_or_folder
docs-doc flow .
```

## Development

```bash
python3 -m pip install -e ".[dev]"
pytest
```
