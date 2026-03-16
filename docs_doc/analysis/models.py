from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class FileRecord:
    relative_path: str
    absolute_path: Path
    suffix: str
    size: int


@dataclass
class RepositoryIndex:
    root: Path
    repo_name: str
    files: list[FileRecord]
    directories: list[str]
    _file_lookup: dict[str, FileRecord] = field(init=False, repr=False)
    _text_cache: dict[str, str | None] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._file_lookup = {record.relative_path: record for record in self.files}

    def has_file(self, relative_path: str) -> bool:
        return relative_path in self._file_lookup

    def get_file(self, relative_path: str) -> FileRecord | None:
        return self._file_lookup.get(relative_path)

    def top_level_directories(self) -> list[str]:
        top_levels = {directory.split("/", 1)[0] for directory in self.directories if directory}
        return sorted(top_levels)

    def read_text(self, relative_path: str, max_chars: int = 200_000) -> str | None:
        if relative_path in self._text_cache:
            return self._text_cache[relative_path]
        record = self.get_file(relative_path)
        if record is None:
            self._text_cache[relative_path] = None
            return None
        try:
            text = record.absolute_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = None
        if text is not None:
            text = text[:max_chars]
        self._text_cache[relative_path] = text
        return text


@dataclass(frozen=True)
class ScriptCommand:
    name: str
    command: str
    source: str
    category: str


@dataclass
class SetupHints:
    install: list[str] = field(default_factory=list)
    run: list[str] = field(default_factory=list)
    test: list[str] = field(default_factory=list)
    env_files: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    docker_files: list[str] = field(default_factory=list)
    ci_files: list[str] = field(default_factory=list)
    missing_signals: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    label: str
    kind: str
    path: str
    importance: int = 1


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    relation: str
    reason: str
    weight: int = 1


@dataclass
class DependencyGraph:
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)


@dataclass
class RepositoryAnalysis:
    root: Path
    repo_name: str
    stack: list[str]
    package_managers: list[str]
    frameworks: list[str]
    important_files: list[str]
    major_folders: list[str]
    scripts: list[ScriptCommand]
    entrypoints: list[str]
    summary: str
    probable_flow: list[str]
    setup: SetupHints
    graph: DependencyGraph
    file_dependencies: dict[str, list[str]] = field(default_factory=dict)
    reverse_file_dependencies: dict[str, list[str]] = field(default_factory=dict)
    monorepo_roots: list[str] = field(default_factory=list)


@dataclass
class PathExplanation:
    target: str
    target_type: str
    purpose: str
    depends_on: list[str]
    used_by: list[str]
    key_files: list[str]
    read_next: list[str]
    notes: list[str] = field(default_factory=list)
