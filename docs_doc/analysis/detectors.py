from __future__ import annotations

import ast
import json
import re
import tomllib
from pathlib import Path

from docs_doc.analysis.models import RepositoryIndex, ScriptCommand, SetupHints

PACKAGE_IMPORTANCE = {
    "README.md": 100,
    "package.json": 95,
    "pyproject.toml": 95,
    "requirements.txt": 90,
    "Dockerfile": 85,
    "docker-compose.yml": 80,
    "docker-compose.yaml": 80,
    ".env.example": 75,
    ".env": 74,
    "Makefile": 74,
}

CODE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
FRAMEWORK_MAP = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "express": "Express",
    "next": "Next.js",
    "react": "React",
    "vue": "Vue",
    "nestjs": "NestJS",
}
STACK_ORDER = {
    "Python": 0,
    "Node.js": 1,
    "Docker": 2,
    "GitHub Actions": 3,
}
SAMPLE_PREFIXES = (
    "tests/fixtures/",
    "test/fixtures/",
    "fixtures/",
    "examples/",
    "example/",
    "samples/",
    "sample/",
)
GENERATED_OUTPUTS = {"REPO_FLOW.md", "REPO_OVERVIEW.md"}
SECONDARY_PREFIXES = (
    "docs/",
    "docs_src/",
    "tests/",
    "test/",
    "data/",
    "scripts/",
    "assets/",
)


def detect_stack(index: RepositoryIndex) -> tuple[list[str], list[str], list[str]]:
    stack: set[str] = set()
    frameworks: set[str] = set()
    package_managers: set[str] = set()

    relevant_files = [record for record in index.files if not _is_sample_path(record.relative_path)]
    files = {record.relative_path for record in relevant_files}

    if any(record.suffix == ".py" for record in relevant_files) or "pyproject.toml" in files or "requirements.txt" in files:
        stack.add("Python")
    if (
        "package.json" in files
        or any(lockfile in files for lockfile in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "pnpm-workspace.yaml"))
        or any(
            record.suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"} and not _is_secondary_path(record.relative_path)
            for record in relevant_files
        )
    ):
        stack.add("Node.js")
    if "Dockerfile" in files or "docker-compose.yml" in files or "docker-compose.yaml" in files:
        stack.add("Docker")
    if any(path.startswith(".github/workflows/") for path in files):
        stack.add("GitHub Actions")

    if "package-lock.json" in files:
        package_managers.add("npm")
    if "yarn.lock" in files:
        package_managers.add("yarn")
    if "pnpm-lock.yaml" in files or "pnpm-workspace.yaml" in files:
        package_managers.add("pnpm")
    if "requirements.txt" in files:
        package_managers.add("pip")

    pyproject_text = index.read_text("pyproject.toml")
    if pyproject_text:
        data = tomllib.loads(pyproject_text)
        if "poetry" in data.get("tool", {}):
            package_managers.add("poetry")
        if "pdm" in data.get("tool", {}):
            package_managers.add("pdm")
        if "hatch" in data.get("tool", {}):
            package_managers.add("hatch")

        project_dependencies = data.get("project", {}).get("dependencies", [])
        poetry_dependencies = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
        for dependency in list(project_dependencies) + list(poetry_dependencies):
            key = dependency.split("[", 1)[0].split(">=", 1)[0].split("==", 1)[0].strip().lower()
            if key in FRAMEWORK_MAP:
                frameworks.add(FRAMEWORK_MAP[key])

    package_text = index.read_text("package.json")
    if package_text:
        package_data = json.loads(package_text)
        dependencies = {}
        dependencies.update(package_data.get("dependencies", {}))
        dependencies.update(package_data.get("devDependencies", {}))
        for dependency_name in dependencies:
            name = dependency_name.lower()
            if name in FRAMEWORK_MAP:
                frameworks.add(FRAMEWORK_MAP[name])

    return (
        sorted(stack, key=lambda item: (STACK_ORDER.get(item, 99), item)),
        sorted(frameworks),
        sorted(package_managers),
    )


def detect_monorepo_roots(index: RepositoryIndex) -> list[str]:
    roots: set[str] = set()
    package_text = index.read_text("package.json")
    if package_text:
        package_data = json.loads(package_text)
        workspaces = package_data.get("workspaces", [])
        if isinstance(workspaces, dict):
            workspaces = workspaces.get("packages", [])
        for workspace in workspaces:
            if workspace.endswith("/*"):
                prefix = workspace[:-2]
                for directory in index.directories:
                    if directory.startswith(f"{prefix}/") and directory.count("/") == prefix.count("/") + 1:
                        roots.add(directory)
            elif workspace in index.directories:
                roots.add(workspace)
    workspace_text = index.read_text("pnpm-workspace.yaml")
    if workspace_text:
        for match in re.finditer(r"-\s+([A-Za-z0-9_./*-]+)", workspace_text):
            pattern = match.group(1).strip().strip("\"'")
            if pattern.endswith("/*"):
                prefix = pattern[:-2]
                for directory in index.directories:
                    if directory.startswith(f"{prefix}/") and directory.count("/") == prefix.count("/") + 1:
                        roots.add(directory)
    return sorted(roots)


def detect_scripts(index: RepositoryIndex) -> list[ScriptCommand]:
    scripts: list[ScriptCommand] = []
    package_text = index.read_text("package.json")
    if package_text:
        package_data = json.loads(package_text)
        for name, command in sorted(package_data.get("scripts", {}).items()):
            scripts.append(
                ScriptCommand(
                    name=name,
                    command=command,
                    source="package.json",
                    category=_categorize_script(name),
                )
            )

    pyproject_text = index.read_text("pyproject.toml")
    if pyproject_text:
        data = tomllib.loads(pyproject_text)
        project_scripts = data.get("project", {}).get("scripts", {})
        poetry_scripts = data.get("tool", {}).get("poetry", {}).get("scripts", {})
        for name, command in sorted({**project_scripts, **poetry_scripts}.items()):
            scripts.append(
                ScriptCommand(
                    name=name,
                    command=str(command),
                    source="pyproject.toml",
                    category="run",
                )
            )

    makefile = index.read_text("Makefile")
    if makefile:
        for line in makefile.splitlines():
            match = re.match(r"^([A-Za-z0-9_.-]+):(?:\s|$)", line)
            if not match:
                continue
            target = match.group(1)
            if target.startswith("."):
                continue
            scripts.append(
                ScriptCommand(
                    name=target,
                    command=f"make {target}",
                    source="Makefile",
                    category=_categorize_script(target),
                )
            )

    return sorted(scripts, key=lambda script: (script.source, script.name))


def detect_important_files(index: RepositoryIndex) -> list[str]:
    root_candidates: list[tuple[int, str]] = []
    nested_candidates: list[tuple[int, str]] = []
    for record in index.files:
        if _is_sample_path(record.relative_path):
            continue
        if Path(record.relative_path).name in GENERATED_OUTPUTS:
            continue
        score = PACKAGE_IMPORTANCE.get(record.relative_path, 0)
        score = max(score, PACKAGE_IMPORTANCE.get(Path(record.relative_path).name, 0))
        if record.relative_path.count("/") == 0:
            score += 40
        if score:
            target = root_candidates if record.relative_path.count("/") == 0 else nested_candidates
            target.append((score, record.relative_path))
        elif record.relative_path.startswith(".github/workflows/"):
            nested_candidates.append((20, record.relative_path))
        elif record.relative_path.endswith((".md", ".yml", ".yaml", ".toml", ".json")) and record.relative_path.count("/") == 0:
            root_candidates.append((45, record.relative_path))
    root_ordered = sorted(root_candidates, key=lambda item: (-item[0], item[1]))
    nested_ordered = sorted(nested_candidates, key=lambda item: (-item[0], item[1]))
    ordered = [path for _, path in root_ordered[:10]]
    if len(ordered) < 10:
        ordered.extend(path for _, path in nested_ordered[: 10 - len(ordered)])
    return ordered[:10]


def detect_entrypoints(index: RepositoryIndex) -> list[str]:
    primary_scores: dict[str, int] = {}
    secondary_scores: dict[str, int] = {}

    def add(path: str, score: int) -> None:
        target = secondary_scores if _is_secondary_path(path) else primary_scores
        _add_entrypoint_score(target, path, score)

    package_text = index.read_text("package.json")
    if package_text:
        package_data = json.loads(package_text)
        for script_name in ("start", "dev", "serve"):
            command = package_data.get("scripts", {}).get(script_name)
            if not command:
                continue
            for token in re.findall(r"[A-Za-z0-9_./-]+\.(?:js|jsx|ts|tsx|mjs|cjs)", command):
                if index.has_file(token):
                    add(token, 100)
        for candidate in (
            "src/index.js",
            "src/index.ts",
            "src/server.js",
            "src/server.ts",
            "src/app.js",
            "src/app.ts",
            "index.js",
            "index.ts",
            "server.js",
            "server.ts",
            "app.js",
            "app.ts",
        ):
            if index.has_file(candidate):
                add(candidate, 70)

    pyproject_text = index.read_text("pyproject.toml")
    if pyproject_text:
        data = tomllib.loads(pyproject_text)
        project_scripts = data.get("project", {}).get("scripts", {})
        poetry_scripts = data.get("tool", {}).get("poetry", {}).get("scripts", {})
        for target in list(project_scripts.values()) + list(poetry_scripts.values()):
            module = str(target).split(":", 1)[0].replace(".", "/")
            candidate = f"{module}.py"
            for maybe in (candidate, f"src/{candidate}"):
                if index.has_file(maybe):
                    add(maybe, 100)
        for candidate in (
            "manage.py",
            "main.py",
            "app.py",
            "src/main.py",
            "src/app.py",
            "app/main.py",
        ):
            if index.has_file(candidate):
                add(candidate, 80)

    for record in index.files:
        if _is_sample_path(record.relative_path):
            continue
        if record.suffix == ".py":
            text = index.read_text(record.relative_path)
            if text and _has_python_main_guard(text):
                score = 60 if not _is_secondary_path(record.relative_path) else 15
                add(record.relative_path, score)
        elif record.relative_path.endswith("__main__.py"):
            score = 85 if not _is_secondary_path(record.relative_path) else 20
            add(record.relative_path, score)

    source_scores = primary_scores or secondary_scores
    ordered = sorted(source_scores.items(), key=lambda item: (-item[1], item[0]))
    return [path for path, _ in ordered[:25]]


def detect_major_folders(index: RepositoryIndex, monorepo_roots: list[str]) -> list[str]:
    if monorepo_roots:
        return monorepo_roots
    primary_scores: dict[str, int] = {}
    primary_code_scores: dict[str, int] = {}
    secondary_scores: dict[str, int] = {}
    for record in index.files:
        if _is_sample_path(record.relative_path):
            continue
        parts = record.relative_path.split("/")
        if len(parts) < 2:
            continue
        top_level = parts[0]
        if top_level.startswith("."):
            continue
        weight = 3 if record.suffix in CODE_EXTENSIONS else 1
        is_secondary = _is_secondary_path(record.relative_path)
        scores = secondary_scores if is_secondary else primary_scores
        scores[top_level] = scores.get(top_level, 0) + weight
        if not is_secondary and record.suffix in CODE_EXTENSIONS:
            primary_code_scores[top_level] = primary_code_scores.get(top_level, 0) + weight
        if Path(index.root / top_level / "__init__.py").exists():
            scores[top_level] += 10
            if not is_secondary:
                primary_code_scores[top_level] = primary_code_scores.get(top_level, 0) + 10
    source_scores = primary_code_scores or primary_scores or secondary_scores
    ordered = sorted(source_scores.items(), key=lambda item: (-item[1], item[0]))
    return [name for name, _ in ordered[:6]]


def _is_sample_path(relative_path: str) -> bool:
    return relative_path.startswith(SAMPLE_PREFIXES)


def _is_secondary_path(relative_path: str) -> bool:
    return relative_path.startswith(SECONDARY_PREFIXES)


def _add_entrypoint_score(scores: dict[str, int], path: str, score: int) -> None:
    existing = scores.get(path, 0)
    if score > existing:
        scores[path] = score


def _has_python_main_guard(text: str) -> bool:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        comparison = node.test
        if not isinstance(comparison, ast.Compare):
            continue
        if len(comparison.ops) != 1 or not isinstance(comparison.ops[0], ast.Eq):
            continue
        if not isinstance(comparison.left, ast.Name) or comparison.left.id != "__name__":
            continue
        if len(comparison.comparators) != 1:
            continue
        comparator = comparison.comparators[0]
        if isinstance(comparator, ast.Constant) and comparator.value == "__main__":
            return True
    return False


def build_setup_hints(
    index: RepositoryIndex,
    stack: list[str],
    package_managers: list[str],
    scripts: list[ScriptCommand],
    entrypoints: list[str],
) -> SetupHints:
    hints = SetupHints()
    hints.env_files = [path for path in (".env", ".env.example", ".env.local") if index.has_file(path)]
    hints.config_files = [
        path
        for path in ("pyproject.toml", "package.json", "requirements.txt", "Makefile", "pnpm-workspace.yaml")
        if index.has_file(path)
    ]
    hints.docker_files = [
        path
        for path in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml")
        if index.has_file(path)
    ]
    hints.ci_files = [path for path in sorted(record.relative_path for record in index.files) if path.startswith(".github/workflows/")]

    if "Python" in stack:
        if "poetry" in package_managers:
            hints.install.append("poetry install")
        elif "requirements.txt" in hints.config_files:
            hints.install.append("python -m pip install -r requirements.txt")
        elif "pyproject.toml" in hints.config_files:
            hints.install.append('python -m pip install -e "."')
        if "tests" in index.top_level_directories():
            hints.test.append("pytest")
        if any(entry.endswith("manage.py") for entry in entrypoints):
            hints.run.append("python manage.py runserver")
        elif entrypoints:
            hints.run.append(f"python {entrypoints[0]}")

    if "Node.js" in stack:
        package_manager = _preferred_node_package_manager(package_managers)
        hints.install.append(f"{package_manager} install")
        if any(script.name == "dev" for script in scripts):
            hints.run.append(f"{package_manager} run dev")
        if any(script.name == "start" for script in scripts):
            hints.run.append(f"{package_manager} run start")
        if any(script.name == "test" for script in scripts):
            hints.test.append(f"{package_manager} run test")

    if not hints.install:
        hints.missing_signals.append("Could not infer a reliable install command.")
    if not hints.run:
        hints.missing_signals.append("Could not infer a reliable run command.")
    if not hints.test:
        hints.missing_signals.append("Could not infer a reliable test command.")
    if not hints.env_files:
        hints.notes.append("No root env example found.")
    if hints.docker_files:
        hints.notes.append("Docker support appears to be available.")
    if hints.ci_files:
        hints.notes.append("CI workflows are present.")
    return hints


def _preferred_node_package_manager(package_managers: list[str]) -> str:
    for name in ("pnpm", "yarn", "npm"):
        if name in package_managers:
            return name
    return "npm"


def _categorize_script(name: str) -> str:
    lowered = name.lower()
    if "test" in lowered:
        return "test"
    if any(token in lowered for token in ("lint", "fmt", "format")):
        return "quality"
    if any(token in lowered for token in ("build", "compile")):
        return "build"
    return "run"
