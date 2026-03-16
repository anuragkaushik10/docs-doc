from __future__ import annotations

from docs_doc.analysis.models import DependencyGraph


def render_mermaid_diagram(graph: DependencyGraph) -> str:
    lines = ["graph TD"]
    for node_id, node in sorted(graph.nodes.items()):
        safe_id = _node_id(node_id)
        label = node.label.replace('"', "'")
        lines.append(f'    {safe_id}["{label}"]')
    for edge in sorted(graph.edges, key=lambda edge: (edge.source, edge.target, edge.relation)):
        source = _node_id(edge.source)
        target = _node_id(edge.target)
        relation = edge.relation.replace("_", " ")
        lines.append(f"    {source} -->|{relation}| {target}")
    return "\n".join(lines)


def _node_id(value: str) -> str:
    cleaned = "".join(character if character.isalnum() else "_" for character in value)
    if cleaned and cleaned[0].isdigit():
        cleaned = f"node_{cleaned}"
    return cleaned or "root"
