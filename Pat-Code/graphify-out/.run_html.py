import json
from graphify.build import build_from_json
from graphify.export import to_html
from pathlib import Path

extraction = json.loads(Path("graphify-out/.graphify_extract.json").read_text(encoding="utf-8"))
analysis   = json.loads(Path("graphify-out/.graphify_analysis.json").read_text(encoding="utf-8"))
labels     = json.loads(Path("graphify-out/.graphify_labels.json").read_text(encoding="utf-8"))

G = build_from_json(extraction, root=".", directed=False)
communities = {int(k): v for k, v in analysis["communities"].items()}
int_labels = {int(k): v for k, v in labels.items()}
member_counts = {int(k): len(v) for k, v in communities.items()}

to_html(G, communities, "graphify-out/graph.html", community_labels=int_labels, member_counts=member_counts)
print(f"HTML generated: {Path('graphify-out/graph.html').stat().st_size:,} bytes")
