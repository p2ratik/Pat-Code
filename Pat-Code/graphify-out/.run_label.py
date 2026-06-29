import sys, json
from graphify.build import build_from_json
from graphify.cluster import score_all
from graphify.analyze import god_nodes, surprising_connections, suggest_questions
from graphify.report import generate
from pathlib import Path

extraction = json.loads(Path("graphify-out/.graphify_extract.json").read_text(encoding="utf-8"))
detection  = json.loads(Path("graphify-out/.graphify_detect.json").read_text(encoding="utf-8"))
analysis   = json.loads(Path("graphify-out/.graphify_analysis.json").read_text(encoding="utf-8"))

G = build_from_json(extraction, root=".", directed=False)
communities = {int(k): v for k, v in analysis["communities"].items()}
cohesion = {int(k): v for k, v in analysis["cohesion"].items()}
tokens = {"input": extraction.get("input_tokens", 0), "output": extraction.get("output_tokens", 0)}

labels = {
    0:  "Patch Application Engine",
    1:  "API Auth & Request Models",
    2:  "Session & Response Utilities",
    3:  "Patch Tool Operations",
    4:  "Core Agent Loop",
    5:  "Auth Service & Profiles",
    6:  "MCP System",
    7:  "Agent Runtime Protocol",
    8:  "DB Models & Auth Service",
    9:  "LLM Client & Event Bus",
    10: "Cloud Database & Cache",
    11: "PAT Service & Profile Cache",
    12: "System Prompts",
    13: "Cloud Agent Runtime",
    14: "MCP Client & Auth",
    15: "CloudAgentRuntime Build",
    16: "Runtime Initialization",
    17: "AgentRuntime Protocol",
    18: "Config & MCPServerConfig",
    19: "FastAPI App & Lifespan",
    20: "Vector Store & Embeddings",
    21: "PAT Service Chat Pipeline",
    22: "API Package Init",
    23: "Root Package Init",
    24: "MCP Package Init",
    25: "Routes Package Init",
}

questions = suggest_questions(G, communities, labels)
report = generate(G, communities, cohesion, labels, analysis["gods"], analysis["surprises"], detection, tokens, ".", suggested_questions=questions)
Path("graphify-out/GRAPH_REPORT.md").write_text(report, encoding="utf-8")
Path("graphify-out/.graphify_labels.json").write_text(json.dumps({str(k): v for k, v in labels.items()}, ensure_ascii=False), encoding="utf-8")
print("Report updated with community labels")
print("Top suggested questions:")
for q in questions[:3]:
    print(" -", q)
