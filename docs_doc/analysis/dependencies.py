from __future__ import annotations

import ast
import re
from pathlib import PurePosixPath

from docs_doc.analysis.models import RepositoryIndex

CODE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}


def build_file_dependency_maps(index: RepositoryIndex) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    file_dependencies: dict[str, set[str]] = {}
    reverse_dependencies: dict[str, set[str]] = {}

    python_map = _build_python_module_map(index)

    for record in index.files:
        if record.suffix not in CODE_SUFFIXES:
            continue
        dependencies = set()
        if record.suffix == ".py":
            dependencies.update(_python_dependencies(index, record.relative_path, python_map))
        else:
            dependencies.update(_javascript_dependencies(index, record.relative_path))
        dependencies.discard(record.relative_path)
        ordered = sorted(dependencies)
        file_dependencies[record.relative_path] = ordered
        for dependency in ordered:
            reverse_dependencies.setdefault(dependency, set()).add(record.relative_path)

    reverse_ordered = {path: sorted(paths) for path, paths in reverse_dependencies.items()}
    return file_dependencies, reverse_ordered


def _build_python_module_map(index: RepositoryIndex) -> dict[str, str]:
    module_map: dict[str, str] = {}
    for record in index.files:
        if record.suffix != ".py":
            continue
        variants = _python_module_variants(record.relative_path)
        for variant in variants:
            module_map.setdefault(variant, record.relative_path)
    return module_map


def _python_module_variants(relative_path: str) -> list[str]:
    parts = list(PurePosixPath(relative_path).parts)
    if not parts:
        return []
    stem = parts[-1][:-3]
    module_parts = parts[:-1]
    if stem != "__init__":
        module_parts = [*module_parts, stem]
    variants = {".".join(module_parts)}
    if module_parts and module_parts[0] == "src":
        variants.add(".".join(module_parts[1:]))
    return sorted(variant for variant in variants if variant)


def _python_dependencies(index: RepositoryIndex, relative_path: str, module_map: dict[str, str]) -> set[str]:
    text = index.read_text(relative_path)
    if not text:
        return set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()

    dependencies: set[str] = set()
    current_package = _current_python_package(relative_path)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                resolved = _resolve_python_module(alias.name, module_map)
                if resolved:
                    dependencies.add(resolved)
        elif isinstance(node, ast.ImportFrom):
            base_module = _resolve_import_from_module(current_package, node.module, node.level)
            candidates: list[str] = []
            if base_module:
                candidates.append(base_module)
                for alias in node.names:
                    if alias.name != "*":
                        candidates.append(f"{base_module}.{alias.name}")
            for candidate in candidates:
                resolved = _resolve_python_module(candidate, module_map)
                if resolved:
                    dependencies.add(resolved)
                    break
    return dependencies


def _current_python_package(relative_path: str) -> list[str]:
    parts = list(PurePosixPath(relative_path).parts)
    stem = parts[-1][:-3]
    if stem == "__init__":
        return parts[:-1]
    return parts[:-1]


def _resolve_import_from_module(current_package: list[str], module: str | None, level: int) -> str | None:
    if level == 0:
        return module
    anchor = list(current_package)
    for _ in range(max(level - 1, 0)):
        if anchor:
            anchor.pop()
    if module:
        anchor.extend(module.split("."))
    return ".".join(part for part in anchor if part)


def _resolve_python_module(module_name: str, module_map: dict[str, str]) -> str | None:
    if module_name in module_map:
        return module_map[module_name]
    if "." in module_name:
        parts = module_name.split(".")
        while len(parts) > 1:
            parts.pop()
            candidate = ".".join(parts)
            if candidate in module_map:
                return module_map[candidate]
    return None


def _javascript_dependencies(index: RepositoryIndex, relative_path: str) -> set[str]:
    text = index.read_text(relative_path)
    if not text:
        return set()
    matches = set()
    patterns = [
        r'import\s+[^;]*?\sfrom\s+[\'"]([^\'"]+)[\'"]',
        r'import\s+[\'"]([^\'"]+)[\'"]',
        r'require\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
        r'export\s+[^;]*?\sfrom\s+[\'"]([^\'"]+)[\'"]',
    ]
    for pattern in patterns:
        matches.update(re.findall(pattern, text))
    resolved = {_resolve_js_specifier(index, relative_path, match) for match in matches}
    return {value for value in resolved if value}


def _resolve_js_specifier(index: RepositoryIndex, relative_path: str, specifier: str) -> str | None:
    if not specifier.startswith("."):
        return None
    parent = PurePosixPath(relative_path).parent
    candidate = parent.joinpath(specifier)
    base = candidate.as_posix()
    possibilities = [base]
    if PurePosixPath(base).suffix:
        possibilities.append(base)
    else:
        for suffix in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
            possibilities.append(f"{base}{suffix}")
            possibilities.append(f"{base}/index{suffix}")
    for possibility in possibilities:
        normalized = PurePosixPath(possibility).as_posix()
        if index.has_file(normalized):
            return normalized
    return None
