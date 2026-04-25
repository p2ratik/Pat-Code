import asyncio
import os
from pathlib import Path
import signal
import sys
from tools.base import Tool, ToolConfirmation, ToolInvocation, Toolkind, ToolResult
from pydantic import BaseModel, Field
import fnmatch

BLOCKED_COMMANDS = {
    "rm -rf /",
    "rm -rf ~",
    "rm -rf /*",
    "dd if=/dev/zero",
    "dd if=/dev/random",
    "mkfs",
    "fdisk",
    "parted",
    ":(){ :|:& };:",  # Fork bomb
    "chmod 777 /",
    "chmod -R 777",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "init 0",
    "init 6",
}


class ShellParams(BaseModel):
    command: str = Field(..., description="The shell command to execute")
    timeout: int = Field(
        10, ge=1, le=20, description="Timeout in seconds (default: 120)"
    )
    cwd: str | None = Field(None, description="Working directory for the command")


class ShellTool(Tool):
    name = "shell"
    kind = Toolkind.SHELL
    description = "Execute a shell command. Use this for running system commands, scripts and CLI tools."

    schema = ShellParams

    async def get_confirmation(
        self, invocation: ToolInvocation
    ) -> ToolConfirmation | None:
        params = ShellParams(**invocation.params)

        for blocked in BLOCKED_COMMANDS:
            if blocked in params.command:
                return ToolConfirmation(
                    tool_name=self.name,
                    params=invocation.params,
                    description=f"Execute (BLOCKED): {params.command}",
                    command=params.command,
                    is_dangerous=True,
                )

        return ToolConfirmation(
            tool_name=self.name,
            params=invocation.params,
            description=f"Execute: {params.command}",
            command=params.command,
            is_dangerous=False,
        )

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = ShellParams(**invocation.params)

        command = params.command.lower().strip()
        for blocked in BLOCKED_COMMANDS:
            if blocked in command:
                return ToolResult.error_result(
                    f"Command blocked for safety: {params.command}",
                    metadata={"blocked": True},
                )

        if params.cwd:
            cwd = Path(params.cwd)
            if not cwd.is_absolute():
                cwd = invocation.cwd / cwd
        else:
            cwd = invocation.cwd

        if not cwd.exists():
            return ToolResult.error_result(f"Working directory doesn't exist: {cwd}")

        env = self._build_environment()
        if sys.platform == "win32":
            shell_cmd = ["cmd.exe", "/c", params.command]
        else:
            shell_cmd = ["/bin/bash", "-c", params.command]

        process = await asyncio.create_subprocess_exec(
            *shell_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
            start_new_session=sys.platform != "win32",
        )

        async def _read_stream(stream: asyncio.StreamReader, buffer: list[str]) -> None:
            max_bytes = 50 * 1024
            collected = 0
            while True:
                try:
                    line = await stream.readline()
                except Exception:
                    break
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace")
                buffer.append(decoded)
                collected += len(decoded)
                if collected >= max_bytes:
                    buffer.append("... [stream truncated]\n")
                    break

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    _read_stream(process.stdout, stdout_lines),
                    _read_stream(process.stderr, stderr_lines),
                ),
                timeout=params.timeout,
            )
            # Process exited within the timeout window
            await process.wait()
            exit_code = process.returncode
            still_running = False

        except asyncio.TimeoutError:
            # Process is still alive — normal for servers
            exit_code = None
            still_running = True

        stdout = "".join(stdout_lines)
        stderr = "".join(stderr_lines)

        # Build output
        output_parts: list[str] = []

        if stdout.strip():
            output_parts.append(stdout.rstrip())

        if stderr.strip():
            output_parts.append("--- stderr ---")
            output_parts.append(stderr.rstrip())

        if still_running:
            output_parts.append(f"--- process still running (pid={process.pid}) ---")
        elif exit_code != 0:
            output_parts.append(f"Exit code: {exit_code}")

        output = "\n".join(output_parts)

        if len(output) > 100 * 1024:
            output = output[: 100 * 1024] + "\n... [output truncated]"

        success = still_running or exit_code == 0

        return ToolResult(
            success=success,
            output=output,
            error=None if still_running else (stderr if exit_code != 0 else None),
            exit_code=exit_code,
            metadata={
                "still_running": still_running,
                "pid": process.pid,
            },
        )

    def _build_environment(self) -> dict[str, str]:
        env = os.environ.copy()

        shell_environment = self.config.shell_environment

        if not shell_environment.ignore_default_excludes:
            for pattern in shell_environment.exclude_patterns:
                keys_to_remove = [
                    k for k in env.keys() if fnmatch.fnmatch(k.upper(), pattern.upper())
                ]

                for k in keys_to_remove:
                    del env[k]

        if shell_environment.set_vars:
            env.update(shell_environment.set_vars)

        return env