from __future__ import annotations

from collections import defaultdict
from pathlib import Path, PurePosixPath

from docs_doc.analysis.dependencies import build_file_dependency_maps
from docs_doc.analysis.detectors import (
    build_setup_hints,
    detect_entrypoints,
    detect_important_files,
    detect_major_folders,
    detect_monorepo_roots,
    detect_project_name,
    detect_scripts,
    detect_stack,
)
from docs_doc.analysis.models import (
    DependencyGraph,
    GraphEdge,
    GraphNode,
    PathExplanation,
    RepositoryAnalysis,
)
from docs_doc.discovery import discover_repository

CENTRAL_CONFIG_NAMES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".env.example",
    ".env",
    "Makefile",
    "pnpm-workspace.yaml",
}
FLOW_EXCLUDED_PREFIXES = (".github/", "tests/", "test/")


def analyze_repository(root: Path) -> RepositoryAnalysis:
    index = discover_repository(root)
    repo_name = detect_project_name(index)
    stack, frameworks, package_managers = detect_stack(index)
    monorepo_roots = detect_monorepo_roots(index)
    scripts = detect_scripts(index)
    important_files = detect_important_files(index)
    entrypoints = detect_entrypoints(index)
    major_folders = detect_major_folders(index, monorepo_roots)
    file_dependencies, reverse_file_dependencies = build_file_dependency_maps(index)
    graph = _build_graph(
        index=index,
        important_files=important_files,
        entrypoints=entrypoints,
        major_folders=major_folders,
        monorepo_roots=monorepo_roots,
        file_dependencies=file_dependencies,
    )
    setup = build_setup_hints(index, stack, package_managers, scripts, entrypoints)
    summary = _build_summary(repo_name, stack, frameworks, entrypoints, major_folders, monorepo_roots)
    probable_flow = _build_probable_flow(graph, entrypoints, frameworks, setup)
    return RepositoryAnalysis(
        root=index.root,
        repo_name=repo_name,
        stack=stack,
        package_managers=package_managers,
        frameworks=frameworks,
        important_files=important_files,
        major_folders=major_folders,
        scripts=scripts,
        entrypoints=entrypoints,
        summary=summary,
        probable_flow=probable_flow,
        setup=setup,
        graph=graph,
        file_dependencies=file_dependencies,
        reverse_file_dependencies=reverse_file_dependencies,
        monorepo_roots=monorepo_roots,
    )


def explain_path(root: Path, target: Path | str) -> PathExplanation:
    analysis = analyze_repository(root)
    index = discover_repository(root)
    relative_target = _normalize_target(root, target)
    absolute_target = root.resolve() / relative_target if relative_target != "." else root.resolve()
    if not absolute_target.exists():
        raise FileNotFoundError(relative_target)
    is_dir = absolute_target.is_dir()
    target_type = "directory" if is_dir else "file"
    depends_on, used_by = _target_edges(analysis, relative_target, is_dir)
    key_files = _target_key_files(index, relative_target, is_dir, analysis)
    read_next = _suggest_next_reads(relative_target, depends_on, key_files, analysis)
    purpose = _describe_target(relative_target, is_dir, analysis, index)
    notes = []
    if not depends_on:
        notes.append("No internal dependency links were detected from this target.")
    if not used_by:
        notes.append("No internal callers or dependents were detected for this target.")
    return PathExplanation(
        target=relative_target,
        target_type=target_type,
        purpose=purpose,
        depends_on=depends_on,
        used_by=used_by,
        key_files=key_files,
        read_next=read_next,
        notes=notes,
    )


def _build_graph(
    *,
    index,
    important_files: list[str],
    entrypoints: list[str],
    major_folders: list[str],
    monorepo_roots: list[str],
    file_dependencies: dict[str, list[str]],
) -> DependencyGraph:
    graph = DependencyGraph()
    central_files = set(entrypoints) | {path for path in CENTRAL_CONFIG_NAMES if index.has_file(path)}
    component_cache: dict[str, str] = {}
    edge_buckets: dict[tuple[str, str, str], dict[str, object]] = {}

    def component_for_path(relative_path: str) -> str:
        if relative_path in component_cache:
            return component_cache[relative_path]
        if relative_path in central_files:
            component = relative_path
        else:
            component = _module_bucket(relative_path, monorepo_roots)
        component_cache[relative_path] = component
        return component

    for relative_path in central_files | set(entrypoints):
        component = component_for_path(relative_path)
        graph.nodes.setdefault(component, _build_node(component, entrypoints, central_files, major_folders, monorepo_roots))

    for source, targets in file_dependencies.items():
        if _is_flow_excluded(source):
            continue
        source_component = component_for_path(source)
        graph.nodes.setdefault(source_component, _build_node(source_component, entrypoints, central_files, major_folders, monorepo_roots))
        for target in targets:
            if _is_flow_excluded(target):
                continue
            target_component = component_for_path(target)
            graph.nodes.setdefault(target_component, _build_node(target_component, entrypoints, central_files, major_folders, monorepo_roots))
            if source_component == target_component:
                continue
            key = (source_component, target_component, "depends_on")
            bucket = edge_buckets.setdefault(key, {"weight": 0, "reasons": set()})
            bucket["weight"] = int(bucket["weight"]) + 1
            bucket["reasons"].add(f"{source} imports {target}")

    for config_path in sorted(central_files & CENTRAL_CONFIG_NAMES):
        for entrypoint in entrypoints:
            source = config_path
            target = component_for_path(entrypoint)
            if source == target:
                continue
            graph.nodes.setdefault(source, _build_node(source, entrypoints, central_files, major_folders, monorepo_roots))
            graph.nodes.setdefault(target, _build_node(target, entrypoints, central_files, major_folders, monorepo_roots))
            key = (source, target, "configures")
            bucket = edge_buckets.setdefault(key, {"weight": 0, "reasons": set()})
            bucket["weight"] = int(bucket["weight"]) + 1
            bucket["reasons"].add(f"{config_path} influences runtime setup")

    graph.edges = [
        GraphEdge(
            source=source,
            target=target,
            relation=relation,
            reason="; ".join(sorted(list(data["reasons"]))[:2]),
            weight=int(data["weight"]),
        )
        for (source, target, relation), data in sorted(edge_buckets.items())
    ]
    return graph


def _build_node(
    component: str,
    entrypoints: list[str],
    central_files: set[str],
    major_folders: list[str],
    monorepo_roots: list[str],
) -> GraphNode:
    if component in entrypoints:
        return GraphNode(node_id=component, label=component, kind="entrypoint", path=component, importance=4)
    if component in central_files:
        return GraphNode(node_id=component, label=component, kind="config", path=component, importance=3)
    if component in monorepo_roots:
        return GraphNode(node_id=component, label=component, kind="workspace", path=component, importance=3)
    if component in major_folders:
        return GraphNode(node_id=component, label=component, kind="module", path=component, importance=2)
    return GraphNode(node_id=component, label=component, kind="module", path=component, importance=1)


def _module_bucket(relative_path: str, monorepo_roots: list[str]) -> str:
    for root in monorepo_roots:
        if relative_path == root or relative_path.startswith(f"{root}/"):
            return root
    parts = PurePosixPath(relative_path).parts
    if len(parts) <= 1:
        return relative_path
    return parts[0]


def _is_flow_excluded(relative_path: str) -> bool:
    return relative_path.startswith(FLOW_EXCLUDED_PREFIXES)


def _build_summary(
    repo_name: str,
    stack: list[str],
    frameworks: list[str],
    entrypoints: list[str],
    major_folders: list[str],
    monorepo_roots: list[str],
) -> str:
    stack_text = ", ".join(stack) if stack else "an unclassified stack"
    framework_text = f" with {', '.join(frameworks)} clues" if frameworks else ""
    entry_text = entrypoints[0] if entrypoints else "no clear entrypoint"
    if monorepo_roots:
        module_text = ", ".join(monorepo_roots[:3])
        return f"{repo_name} looks like a {stack_text} monorepo{framework_text}. The most obvious package roots are {module_text}, and the likely starting point is {entry_text}."
    if major_folders:
        module_text = ", ".join(major_folders[:3])
        return f"{repo_name} looks like a {stack_text} project{framework_text}. The main code seems to live in {module_text}, and the likely starting point is {entry_text}."
    return f"{repo_name} looks like a {stack_text} project{framework_text}, but the structure is sparse enough that only a light overview was inferred."


def _build_probable_flow(
    graph: DependencyGraph,
    entrypoints: list[str],
    frameworks: list[str],
    setup,
) -> list[str]:
    lines: list[str] = []
    if entrypoints:
        first = entrypoints[0]
        outgoing = [edge.target for edge in graph.edges if edge.source == first and edge.relation == "depends_on"]
        if outgoing:
            lines.append(f"`{first}` appears to fan into {', '.join(outgoing[:3])}.")
        else:
            lines.append(f"`{first}` looks like the main bootstrap point.")
    config_edges = [edge for edge in graph.edges if edge.relation == "configures"]
    if config_edges:
        config_sources = ", ".join(sorted({edge.source for edge in config_edges})[:3])
        lines.append(f"Runtime setup is shaped by {config_sources}.")
    if frameworks:
        lines.append(f"Framework clues suggest a {', '.join(frameworks)}-style application layout.")
    if setup.env_files:
        lines.append(f"Environment configuration likely starts in {', '.join(setup.env_files[:2])}.")
    return lines or ["The dependency evidence is light, so the flow summary is intentionally conservative."]


def _normalize_target(root: Path, target: Path | str) -> str:
    path = Path(target)
    absolute = path if path.is_absolute() else (root / path)
    relative = absolute.resolve().relative_to(root.resolve())
    return "." if str(relative) == "." else relative.as_posix()


def _target_edges(analysis: RepositoryAnalysis, relative_target: str, is_dir: bool) -> tuple[list[str], list[str]]:
    if not is_dir:
        depends_on = analysis.file_dependencies.get(relative_target, [])
        used_by = analysis.reverse_file_dependencies.get(relative_target, [])
        return depends_on[:6], used_by[:6]

    prefix = f"{relative_target}/"
    dependency_counter: dict[str, int] = defaultdict(int)
    reverse_counter: dict[str, int] = defaultdict(int)
    for source, targets in analysis.file_dependencies.items():
        if source.startswith(prefix):
            for target in targets:
                bucket = _module_bucket(target, analysis.monorepo_roots)
                if bucket != relative_target:
                    dependency_counter[bucket] += 1
        elif any(target.startswith(prefix) for target in targets):
            bucket = _module_bucket(source, analysis.monorepo_roots)
            if bucket != relative_target:
                reverse_counter[bucket] += 1
    depends_on = [name for name, _ in sorted(dependency_counter.items(), key=lambda item: (-item[1], item[0]))[:6]]
    used_by = [name for name, _ in sorted(reverse_counter.items(), key=lambda item: (-item[1], item[0]))[:6]]
    return depends_on, used_by


def _target_key_files(index, relative_target: str, is_dir: bool, analysis: RepositoryAnalysis) -> list[str]:
    if not is_dir:
        parent = PurePosixPath(relative_target).parent.as_posix()
        if parent == ".":
            parent = ""
        siblings = [
            record.relative_path
            for record in index.files
            if PurePosixPath(record.relative_path).parent.as_posix() == parent and record.relative_path != relative_target
        ]
        preferred = [path for path in siblings if path in analysis.entrypoints or path in analysis.important_files]
        return (preferred + siblings)[:5]

    prefix = "" if relative_target == "." else f"{relative_target}/"
    children = [record.relative_path for record in index.files if record.relative_path.startswith(prefix)]
    ranked = sorted(
        children,
        key=lambda path: (
            0 if path in analysis.entrypoints else 1,
            0 if path in analysis.important_files else 1,
            path.count("/"),
            path,
        ),
    )
    return ranked[:6]


def _suggest_next_reads(
    relative_target: str,
    depends_on: list[str],
    key_files: list[str],
    analysis: RepositoryAnalysis,
) -> list[str]:
    suggestions: list[str] = []
    if relative_target in analysis.entrypoints:
        suggestions.extend(depends_on)
    suggestions.extend(key_files)
    for important in analysis.important_files:
        if important != relative_target:
            suggestions.append(important)
    deduped: list[str] = []
    for item in suggestions:
        if item and item not in deduped:
            deduped.append(item)
    return deduped[:6]


def _describe_target(relative_target: str, is_dir: bool, analysis: RepositoryAnalysis, index) -> str:
    if relative_target in analysis.entrypoints:
        return f"`{relative_target}` looks like a primary bootstrap or runtime entrypoint."
    if relative_target in CENTRAL_CONFIG_NAMES:
        return f"`{relative_target}` looks like a central configuration or packaging file."
    name = PurePosixPath(relative_target).name.lower()
    if is_dir:
        child_count = sum(1 for record in index.files if record.relative_path.startswith(f"{relative_target}/"))
        if relative_target in analysis.major_folders:
            return f"`{relative_target}` is one of the main code areas in this repo, with {child_count} tracked files beneath it."
        return f"`{relative_target}` is a supporting directory with {child_count} tracked files."
    if name.startswith("test_") or "/tests/" in relative_target or relative_target.startswith("tests/"):
        return f"`{relative_target}` looks like a test file."
    if name in {"main.py", "app.py", "server.js", "index.js", "index.ts"}:
        return f"`{relative_target}` looks like application bootstrap code."
    if name.endswith(".md"):
        return f"`{relative_target}` looks like documentation."
    dependencies = analysis.file_dependencies.get(relative_target, [])
    if dependencies:
        return f"`{relative_target}` appears to coordinate code from {', '.join(dependencies[:3])}."
    return f"`{relative_target}` is present in the repo, but its role could only be inferred from its location and filename."
