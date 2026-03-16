from __future__ import annotations

import os
from pathlib import Path

from docs_doc.analysis.models import FileRecord, RepositoryIndex

IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".idea",
    ".vscode",
    ".next",
    ".turbo",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".pytest_cache",
}


def discover_repository(root: Path) -> RepositoryIndex:
    root = root.resolve()
    files: list[FileRecord] = []
    directories: set[str] = set()

    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in IGNORED_DIRECTORIES and not name.endswith(".egg-info")
        )
        current_path = Path(current_root)
        if current_path != root:
            directories.add(current_path.relative_to(root).as_posix())

        for filename in sorted(filenames):
            if filename == ".DS_Store":
                continue
            absolute_path = current_path / filename
            try:
                size = absolute_path.stat().st_size
            except OSError:
                continue
            relative_path = absolute_path.relative_to(root).as_posix()
            files.append(
                FileRecord(
                    relative_path=relative_path,
                    absolute_path=absolute_path,
                    suffix=absolute_path.suffix.lower(),
                    size=size,
                )
            )

    return RepositoryIndex(
        root=root,
        repo_name=root.name,
        files=sorted(files, key=lambda record: record.relative_path),
        directories=sorted(directories),
    )
