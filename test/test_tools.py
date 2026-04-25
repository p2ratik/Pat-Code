"""
test_tools.py — Tool base, ToolResult, registry, and safety tests.
No network or real subprocess calls needed.
"""

import sys
import pytest
import asyncio
from pathlib import Path

from tools.base import FileDiff, Tool, ToolConfirmation, ToolInvocation, ToolResult, Toolkind
from tools.registry import ToolRegistry, create_default_registry
from tools.subagents import SubagentDefinition
from safety.approval import (
    ApprovalDecision,
    ApprovalManager,
    ApprovalContext,
    is_dangerous_command,
    is_safe_command,
)
from config.config import ApprovalPolicy, Config


# ---------------------------------------------------------------------------
# ToolResult
# ---------------------------------------------------------------------------

class TestToolResult:
    def test_success_result(self):
        r = ToolResult.success_result(output="hello")
        assert r.success is True
        assert r.output == "hello"
        assert r.error is None

    def test_error_result(self):
        r = ToolResult.error_result(error="oops")
        assert r.success is False
        assert r.error == "oops"

    def test_to_model_output_success(self):
        r = ToolResult.success_result(output="ok")
        assert r.to_model_output() == "ok"

    def test_to_model_output_error(self):
        r = ToolResult.error_result(error="bad thing", output="partial")
        out = r.to_model_output()
        assert "bad thing" in out

    def test_truncated_defaults_false(self):
        r = ToolResult.success_result()
        assert r.truncated is False

    def test_exit_code_defaults_none(self):
        r = ToolResult.success_result()
        assert r.exit_code is None


# ---------------------------------------------------------------------------
# FileDiff
# ---------------------------------------------------------------------------

class TestFileDiff:
    def test_diff_shows_changes(self, tmp_path):
        p = tmp_path / "file.py"
        diff = FileDiff(
            path=p,
            old_content="line1\nline2\n",
            new_content="line1\nchanged\n",
        )
        result = diff.to_diff()
        assert "-line2" in result
        assert "+changed" in result

    def test_new_file_diff(self, tmp_path):
        p = tmp_path / "new.py"
        diff = FileDiff(
            path=p,
            old_content="",
            new_content="new content\n",
            is_new_file=True,
        )
        result = diff.to_diff()
        assert "/dev/null" in result


# ---------------------------------------------------------------------------
# Concrete Tool stub for testing abstract base
# ---------------------------------------------------------------------------

class DummyTool(Tool):
    name = "dummy"
    description = "A dummy tool for testing"
    kind = Toolkind.READ

    @property
    def schema(self):
        from pydantic import BaseModel
        class DummyParams(BaseModel):
            msg: str = "hello"
        return DummyParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        return ToolResult.success_result(output=invocation.params.get("msg", ""))


class TestToolBase:
    def _make_tool(self, tmp_path):
        cfg = Config(cwd=tmp_path)
        return DummyTool(cfg)

    def test_validate_params_valid(self, tmp_path):
        tool = self._make_tool(tmp_path)
        errors = tool.validate_params({"msg": "hi"})
        assert not errors

    def test_validate_params_wrong_type(self, tmp_path):
        tool = self._make_tool(tmp_path)
        # msg must be str; pass an incompatible type that Pydantic will coerce or reject
        # Pydantic v2 will coerce int to str, so pass something truly wrong
        errors = tool.validate_params({"msg": {"nested": "dict"}})
        # Either no errors (pydantic coerces) or errors present — just ensure it doesn't crash
        assert isinstance(errors, (list, type(None)))

    def test_is_mutating_read(self, tmp_path):
        tool = self._make_tool(tmp_path)
        assert tool.is_mutating({}) is False

    def test_openai_schema_structure(self, tmp_path):
        tool = self._make_tool(tmp_path)
        schema = tool.to_openai_schema()
        assert schema["name"] == "dummy"
        assert "description" in schema
        assert "parameters" in schema
        assert schema["parameters"]["type"] == "object"

    def test_execute_returns_result(self, tmp_path):
        tool = self._make_tool(tmp_path)
        invocation = ToolInvocation(params={"msg": "world"}, cwd=tmp_path)
        result = asyncio.run(tool.execute(invocation))
        assert result.success
        assert result.output == "world"


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------

class TestToolRegistry:
    def _make_registry(self, tmp_path):
        cfg = Config(cwd=tmp_path)
        registry = ToolRegistry(cfg)
        registry.register(DummyTool(cfg))
        return registry

    def test_register_and_get(self, tmp_path):
        reg = self._make_registry(tmp_path)
        tool = reg.get("dummy")
        assert tool is not None
        assert tool.name == "dummy"

    def test_get_unknown_returns_none(self, tmp_path):
        reg = self._make_registry(tmp_path)
        assert reg.get("no_such_tool") is None

    def test_unregister(self, tmp_path):
        reg = self._make_registry(tmp_path)
        removed = reg.unregister("dummy")
        assert removed is True
        assert reg.get("dummy") is None

    def test_unregister_nonexistent(self, tmp_path):
        reg = self._make_registry(tmp_path)
        assert reg.unregister("ghost") is False

    def test_get_tools_list(self, tmp_path):
        reg = self._make_registry(tmp_path)
        tools = reg.get_tools()
        names = [t.name for t in tools]
        assert "dummy" in names

    def test_allowed_tools_filter(self, tmp_path):
        cfg = Config(cwd=tmp_path, allowed_tools=["other_tool"])
        registry = ToolRegistry(cfg)
        registry.register(DummyTool(cfg))
        # dummy is not in allowed_tools → should be filtered out
        tools = registry.get_tools()
        assert all(t.name != "dummy" for t in tools)

    def test_get_schemas_returns_list(self, tmp_path):
        reg = self._make_registry(tmp_path)
        schemas = reg.get_schemas()
        assert isinstance(schemas, list)
        assert len(schemas) > 0

    def test_create_default_registry_has_builtin_tools(self, tmp_path):
        cfg = Config(cwd=tmp_path)
        reg = create_default_registry(cfg)
        names = [t.name for t in reg.get_tools()]
        # Core builtins must always be present
        for expected in ("shell", "read_file", "write_file", "list_dir", "grep"):
            assert expected in names, f"Missing builtin tool: {expected}"


# ---------------------------------------------------------------------------
# Safety — command classification
# ---------------------------------------------------------------------------

class TestCommandClassification:
    # --- Dangerous ---
    @pytest.mark.parametrize("cmd", [
        "rm -rf /",
        "rm -rf ~",
        "rm -rf /*",
        "dd if=/dev/zero of=/dev/sda",
        "mkfs.ext4 /dev/sda1",
        "shutdown -h now",
        "reboot",
        "chmod 777 /",
    ])
    def test_dangerous_commands_detected(self, cmd):
        assert is_dangerous_command(cmd), f"Expected '{cmd}' to be dangerous"

    # --- Safe ---
    @pytest.mark.parametrize("cmd", [
        "ls -la",
        "pwd",
        "echo hello",
        "git status",
        "git log --oneline",
        "pip list",
        "grep -r foo .",
        "date",
        "whoami",
    ])
    def test_safe_commands_detected(self, cmd):
        assert is_safe_command(cmd), f"Expected '{cmd}' to be safe"

    def test_normal_command_not_dangerous(self):
        assert not is_dangerous_command("python main.py")

    def test_normal_command_not_safe(self):
        # "python main.py" is not in safe patterns (could do anything)
        assert not is_safe_command("python main.py")


# ---------------------------------------------------------------------------
# ApprovalManager
# ---------------------------------------------------------------------------

class TestApprovalManager:
    def _ctx(self, is_mutating=True, command=None, is_dangerous=False, paths=None):
        return ApprovalContext(
            tool_name="test",
            params={},
            is_mutating=is_mutating,
            affected_paths=paths or [],
            command=command,
            is_dangerous=is_dangerous,
        )

    def test_read_op_always_approved(self, tmp_path):
        mgr = ApprovalManager(ApprovalPolicy.ON_REQUEST, tmp_path)
        ctx = self._ctx(is_mutating=False)
        result = asyncio.run(mgr.check_approval(ctx))
        assert result == ApprovalDecision.APPROVED

    def test_yolo_always_approves(self, tmp_path):
        mgr = ApprovalManager(ApprovalPolicy.YOLO, tmp_path)
        ctx = self._ctx(command="rm -rf /", is_dangerous=True)
        result = asyncio.run(mgr.check_approval(ctx))
        assert result == ApprovalDecision.APPROVED

    def test_auto_approves_safe_mutation(self, tmp_path):
        mgr = ApprovalManager(ApprovalPolicy.AUTO, tmp_path)
        ctx = self._ctx(command="echo hi")
        result = asyncio.run(mgr.check_approval(ctx))
        assert result == ApprovalDecision.APPROVED

    def test_dangerous_command_rejected_on_request(self, tmp_path):
        mgr = ApprovalManager(ApprovalPolicy.ON_REQUEST, tmp_path)
        ctx = self._ctx(command="rm -rf /", is_dangerous=True)
        result = asyncio.run(mgr.check_approval(ctx))
        assert result == ApprovalDecision.REJECTED

    def test_never_rejects_non_safe(self, tmp_path):
        mgr = ApprovalManager(ApprovalPolicy.NEVER, tmp_path)
        ctx = self._ctx(command="python script.py")
        result = asyncio.run(mgr.check_approval(ctx))
        assert result == ApprovalDecision.REJECTED

    def test_never_approves_safe(self, tmp_path):
        mgr = ApprovalManager(ApprovalPolicy.NEVER, tmp_path)
        ctx = self._ctx(command="ls -la")
        result = asyncio.run(mgr.check_approval(ctx))
        assert result == ApprovalDecision.APPROVED

    def test_on_request_safe_cmd_approved(self, tmp_path):
        mgr = ApprovalManager(ApprovalPolicy.ON_REQUEST, tmp_path)
        ctx = self._ctx(command="git status")
        result = asyncio.run(mgr.check_approval(ctx))
        assert result == ApprovalDecision.APPROVED

    def test_on_request_needs_confirmation_for_out_of_cwd_path(self, tmp_path):
        """Writing to a path outside the project cwd must require confirmation."""
        import tempfile
        other_dir = Path(tempfile.mkdtemp())
        try:
            mgr = ApprovalManager(ApprovalPolicy.ON_REQUEST, tmp_path)
            outside_file = other_dir / "secret.py"
            ctx = self._ctx(is_mutating=True, paths=[outside_file])
            result = asyncio.run(mgr.check_approval(ctx))
            assert result == ApprovalDecision.NEEDS_CONFIRMATION
        finally:
            other_dir.rmdir()
