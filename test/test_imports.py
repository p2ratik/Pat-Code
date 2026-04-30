"""
test_imports.py — CI smoke test
Ensures every core module can be imported without errors.
No credentials or network access required.
"""

import importlib
import pytest


MODULES = [
    # Config layer
    "config.config",
    "config.loader",
    "config.credentials",
    # Client layer
    "client.response",
    "client.llm_client",
    # Agent layer
    "agent.events",
    "agent.persistence",
    "agent.session",
    "agent.agent",
    # Tools — base & registry
    "tools.base",
    "tools.registry",
    "tools.discovery",
    # Tools — builtins
    "tools.builtins",
    "tools.builtins.read_file",
    "tools.builtins.write_file",
    "tools.builtins.edit_file",
    "tools.builtins.shell",
    "tools.builtins.list_dir",
    "tools.builtins.grep",
    "tools.builtins.glob",
    "tools.builtins.web_search",
    "tools.builtins.web_fetch",
    "tools.builtins.memory",
    "tools.builtins.todo",
    # Tools — MCP
    "tools.mcp.client",
    "tools.mcp.mcp_manager",
    "tools.mcp.mcp_tool",
    # Tools — subagents
    "tools.subagents",
    # Safety
    "safety.approval",
    # Utils
    "utils.errors",
    "utils.text",
    "utils.paths",
    # DB
    "db.database",
    # apply_patch
    "apply_patch",
    # vectorstore
    "vector_store.memory_manager"
]


@pytest.mark.parametrize("module_name", MODULES)
def test_module_imports(module_name):
    """Each module must import cleanly."""
    mod = importlib.import_module(module_name)
    assert mod is not None


def test_package_version():
    """__version__ must be a non-empty string."""
    import importlib.metadata
    version = importlib.metadata.version("pat-agent")
    assert isinstance(version, str)
    assert version  # not empty
    # Must follow semver-ish pattern (e.g. "0.1.3")
    parts = version.split(".")
    assert len(parts) >= 2, f"Unexpected version format: {version}"
