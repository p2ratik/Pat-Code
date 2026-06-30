import pytest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path

from agent.hooks.base import ExecutionContext, ExecutionState, RetryMode, VerificationResult
from agent.hooks.verification import VerificationHook
from agent.execution_engine import ExecutionEngine
from tools.base import ExecutionResult, ToolResult, Tool, Toolkind

@pytest.fixture
def mock_tool():
    tool = MagicMock(spec=Tool)
    tool.name = "mock_tool"
    tool.kind = Toolkind.READ
    tool.requires_semantic_verification = False
    return tool

@pytest.fixture
def base_context(mock_tool):
    return ExecutionContext(
        tool_name="mock_tool",
        tool=mock_tool,
        tool_kind=mock_tool.kind,
        params={"test": "val"},
        cwd=Path("/tmp"),
        session=MagicMock(),
    )

@pytest.fixture
def mock_runtime():
    runtime = MagicMock()
    runtime.tool_registry = MagicMock()
    runtime.tool_registry.invoke = AsyncMock()
    return runtime

@pytest.mark.asyncio
async def test_verification_hook_success(base_context):
    hook = VerificationHook()
    tool_result = ToolResult.success_result(output="valid output")
    exec_result = ExecutionResult(tool_result=tool_result)

    result = await hook.after_execute(base_context, exec_result)

    assert base_context.state.verification is not None
    assert base_context.state.verification.passed is True
    assert base_context.state.verification.confidence == 1.0
    assert len(base_context.state.verification.issues) == 0

@pytest.mark.asyncio
async def test_verification_hook_empty_output(base_context):
    hook = VerificationHook()
    tool_result = ToolResult.success_result(output="   ")
    exec_result = ExecutionResult(tool_result=tool_result)

    result = await hook.after_execute(base_context, exec_result)

    assert base_context.state.verification.passed is False
    assert "Tool succeeded but returned empty output" in base_context.state.verification.issues
    assert base_context.state.verification.retry_mode == RetryMode.ENGINE

@pytest.mark.asyncio
async def test_verification_hook_shell_exit_code(base_context):
    hook = VerificationHook()
    base_context.tool_name = "shell"
    tool_result = ToolResult.success_result(output="error log", exit_code=1)
    exec_result = ExecutionResult(tool_result=tool_result)

    result = await hook.after_execute(base_context, exec_result)

    assert base_context.state.verification.passed is False
    assert "Non-zero exit code: 1" in base_context.state.verification.issues

@pytest.mark.asyncio
async def test_verification_hook_malformed_json(base_context):
    hook = VerificationHook()
    tool_result = ToolResult.success_result(output="{ 'bad_json': true ")
    exec_result = ExecutionResult(tool_result=tool_result)

    result = await hook.after_execute(base_context, exec_result)

    assert base_context.state.verification.passed is False
    assert any("fails to parse" in issue for issue in base_context.state.verification.issues)

@pytest.mark.asyncio
async def test_execution_engine_pipeline(mock_runtime, mock_tool):
    mock_runtime.tool_registry.get.return_value = mock_tool
    
    mock_tool_result = ToolResult.success_result(output="test")
    mock_runtime.tool_registry.invoke.return_value = mock_tool_result

    mock_hook = AsyncMock()
    mock_hook.after_execute.return_value = ExecutionResult(tool_result=mock_tool_result)
    
    engine = ExecutionEngine(runtime=mock_runtime, hooks=[mock_hook])
    
    result = await engine.execute(
        name="mock_tool",
        params={},
        cwd=Path("/tmp"),
        session=None,
    )

    mock_hook.before_execute.assert_called_once()
    mock_hook.after_execute.assert_called_once()
    mock_runtime.tool_registry.invoke.assert_called_once()

    assert result.attempts == 1
    assert result.success is True

@pytest.mark.asyncio
async def test_execution_engine_retry_loop(mock_runtime, mock_tool):
    mock_runtime.tool_registry.get.return_value = mock_tool
    mock_runtime.tool_registry.invoke.return_value = ToolResult.success_result(output="test")

    class RetrySignalingHook:
        async def before_execute(self, ctx):
            ctx.max_attempts = 3

        async def after_execute(self, ctx, result):
            if ctx.attempt == 1:
                ctx.state.retry_requested = True
            return result

    engine = ExecutionEngine(runtime=mock_runtime, hooks=[RetrySignalingHook()])
    
    result = await engine.execute("mock_tool", {}, Path("/tmp"), None)

    assert mock_runtime.tool_registry.invoke.call_count == 2
    assert result.attempts == 2
    assert result.recovered is True

from agent.hooks.retry import RetryHook

@pytest.mark.asyncio
async def test_retry_hook_engine_mode(base_context):
    hook = RetryHook(max_attempts=3)
    await hook.before_execute(base_context)
    
    base_context.state.verification = VerificationResult(
        passed=False,
        confidence=0.0,
        issues=["Tool succeeded but returned empty output"],
        retry_mode=RetryMode.ENGINE,
        repair_instruction="SYSTEM REPAIR NOTICE\nTool: mock_tool\nIssue: Empty output",
    )
    
    tool_result = ToolResult.success_result(output="   ")
    exec_result = ExecutionResult(tool_result=tool_result)
    
    result = await hook.after_execute(base_context, exec_result)
    
    assert base_context.state.retry_requested is True
    assert "SYSTEM REPAIR NOTICE" not in result.tool_result.output

@pytest.mark.asyncio
async def test_retry_hook_agent_mode(base_context):
    hook = RetryHook(max_attempts=3)
    await hook.before_execute(base_context)
    
    repair_msg = "SYSTEM REPAIR NOTICE\nTool: mock_tool\nIssue: SyntaxError"
    base_context.state.verification = VerificationResult(
        passed=False,
        confidence=0.0,
        issues=["Non-zero exit code: 1"],
        retry_mode=RetryMode.AGENT,
        repair_instruction=repair_msg,
    )
    
    tool_result = ToolResult.success_result(output="error log", exit_code=1)
    exec_result = ExecutionResult(tool_result=tool_result)
    
    result = await hook.after_execute(base_context, exec_result)
    
    assert base_context.state.retry_requested is False
    assert result.repair_instruction == repair_msg

@pytest.mark.asyncio
async def test_retry_hook_none_mode(base_context):
    hook = RetryHook(max_attempts=3)
    await hook.before_execute(base_context)
    
    base_context.state.verification = VerificationResult(
        passed=True,
        confidence=1.0,
        issues=[],
        retry_mode=RetryMode.NONE,
    )
    
    tool_result = ToolResult.success_result(output="valid")
    exec_result = ExecutionResult(tool_result=tool_result)
    
    result = await hook.after_execute(base_context, exec_result)
    
    assert base_context.state.retry_requested is False
    assert result.tool_result.output == "valid"

@pytest.mark.asyncio
async def test_retry_hook_exhaustion(base_context):
    hook = RetryHook(max_attempts=2)
    await hook.before_execute(base_context)
    
    base_context.attempt = 2
    base_context.state.verification = VerificationResult(
        passed=False,
        confidence=0.0,
        issues=["Empty"],
        retry_mode=RetryMode.ENGINE,
        repair_instruction="Repair msg",
    )
    
    tool_result = ToolResult.success_result(output=" ")
    exec_result = ExecutionResult(tool_result=tool_result)
    
    result = await hook.after_execute(base_context, exec_result)
    
    assert base_context.state.retry_requested is False
