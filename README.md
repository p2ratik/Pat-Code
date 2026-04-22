# PAT Agent

PAT is an AI coding agent built from scratch in Python. It provides an interactive CLI, a tool-driven agentic execution loop, support for MCP servers, and composable subagents for specialized tasks.

## What This Agent Can Do

- Run in interactive chat mode or single-prompt mode.
- Use built-in tools to read/edit files, run shell commands, search code, use web utilities, and manage memory/todos.
- Connect to external MCP servers and expose their tools to the model.
- Execute default and user-defined subagents as callable tools.
- Enforce safety policies for mutating operations through approval modes.
- Save, resume, checkpoint, and restore sessions.

## Architectural Pattern

PAT follows a session-oriented, event-driven agentic loop.

### Core Pattern

1. User input enters the CLI.
2. A `Session` initializes model client, tool registry, MCP manager, discovery, context manager, and safety manager.
3. The `Agent` runs an iterative loop (`max_turns`):
	 - Send context + tool schemas to the model.
	 - Stream text deltas.
	 - Collect tool calls.
	 - Invoke tools with validation and approval checks.
	 - Feed tool results back into context.
4. The loop exits when no further tool calls are requested or max turns are reached.

### Main Components

- `main.py`: CLI entrypoint and command handling.
- `agent/agent.py`: core agentic loop and event emission.
- `agent/session.py`: runtime composition root for each session.
- `context/manager.py`: conversation state and token accounting.
- `tools/registry.py`: tool registration, schema exposure, invocation, approval checks.
- `tools/mcp/*`: MCP client/manager and MCP tool adapter.
- `tools/subagents.py`: subagent tool implementation and default subagents.
- `safety/approval.py`: policy-based approval decisions.
- `config/*`: config model, loader, and secure credential storage.

## Installation

### Requirements

- Python 3.11+
- Windows, macOS, or Linux

### Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -e .
```

This installs the CLI command:

```bash
pat-agent
```

## Quick Start

1. Configure credentials (stored in OS keyring):

```bash
pat-agent configure apikey <YOUR_API_KEY>
pat-agent configure baseurl <YOUR_BASE_URL>
```

2. Verify stored credentials:

```bash
pat-agent configure show
```

3. Start interactive mode:

```bash
pat-agent
```

4. Or run one prompt and exit:

```bash
pat-agent --prompt "Summarize this repository"
```

## Configuration

PAT supports system-level and project-level configuration.

### Config File Locations

- System config: `<platform config dir>/ai-agent/config.toml`
- Project config: `<project-root>/.ai-agent/config.toml`

Project config overrides system config.

### Credential Resolution

For both API key and base URL:

1. OS keyring value takes priority.
2. Environment variable fallback is used if keyring is empty.

Environment variables:

- `API_KEY`
- `BASE_URL`

### Example `config.toml`

```toml
max_turns = 100
approval = "on-request"
allowed_tools = ["read_file", "list_dir", "grep", "glob", "shell"]

[model]
name = "elephant-alpha"
temperature = 1.0
context_window = 256000

[shell_environment]
ignore_default_excludes = false
exclude_patterns = ["*KEY*", "*TOKEN*", "*SECRET*"]

[shell_environment.set_vars]
ENV = "dev"

[mcp_servers.filesystem]
enabled = true
startup_timeout_sec = 10
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "."]

[[user_subagents]]
name = "doc_writer"
description = "Writes or improves project docs"
goal_prompt = "You are a documentation specialist. Produce clear, concise technical docs."
allowed_tools = ["read_file", "glob", "grep", "write_file", "edit"]
max_turns = 20
timeout_seconds = 600
```

### Approval Modes

Supported values:

- `on-request`
- `on-failure`
- `auto`
- `auto-edit`
- `never`
- `yolo`

## Commands Reference

### CLI Commands

```bash
pat-agent [--prompt "..."] [--cwd <path>]
```

- `--prompt`, `-p`: run one prompt non-interactively and exit.
- `--cwd`, `-c`: set working directory for this run.

### Credential Commands

```bash
pat-agent configure apikey <value>
pat-agent configure baseurl <value>
pat-agent configure show
pat-agent configure delete apikey
pat-agent configure delete baseurl
```

- `configure apikey`: stores API key in OS keyring.
- `configure baseurl`: stores base URL in OS keyring.
- `configure show`: displays stored values (API key masked).
- `configure delete`: removes stored credential.

### Interactive Slash Commands

Available while running `pat-agent` in interactive mode:

- `/help`: show commands.
- `/clear`: clear conversation context.
- `/config`: print current runtime config.
- `/model <name>`: change model name for current session.
- `/approval <policy>`: change approval mode for current session.
- `/tools`: list available tools (built-in + MCP + subagent tools).
- `/mcp`: show MCP server connection status and tool count.
- `/stats`: show session stats.
- `/save`: save session snapshot.
- `/sessions`: list saved sessions.
- `/resume <session_id>`: resume a saved session.
- `/checkpoint`: create checkpoint for current session.
- `/listcheckpoints`: list checkpoints for current session.
- `/restore <checkpoint_id>`: restore from checkpoint.
- `/exit` or `/quit`: exit the CLI.

## Tools: Built-in Capabilities

PAT registers these built-in tools by default:

- `read_file(path, offset=1, limit=None)`
- `write_file(path, content, create_directories=true)`
- `edit(path, old_string, new_string, replace_all=false)`
- `shell(command, timeout=10, cwd=None)`
- `list_dir(path=".", include_hidden=false)`
- `grep(pattern, path=".", case_insensitive=false)`
- `glob(pattern, path=".")`
- `web_search(query, max_results=10)`
- `web_fetch(url, timeout=30)`
- `todos(action, id=None, content=None)`
- `memory(action, key=None, value=None)`
- `apply_patch(patch, dry_run=false)`

Notes:

- Mutating tools pass through approval/safety checks.
- `allowed_tools` can restrict tool visibility at runtime.

## MCP Support

PAT can connect to multiple MCP servers via config.

### MCP Transport Options

Each server must use exactly one of:

- `command` + `args` (+ optional `env`, `cwd`) for stdio transport
- `url` for HTTP/SSE transport

### MCP Tool Naming

Connected MCP tools are registered under:

- `<server_name>__<tool_name>`

This avoids name collisions and makes source server explicit.

## Subagents

Subagents are exposed as tools and run isolated focused tasks with their own constrained config.

### Default Subagents

- `subagent_codebase_investigator`
- `subagent_code_reviewer`

### Create Your Own Subagents

Add one or more `[[user_subagents]]` blocks in `config.toml`.

Required fields:

- `name`
- `description`
- `goal_prompt`

Optional fields:

- `allowed_tools`
- `max_turns`
- `timeout_seconds`

When loaded, each user subagent is registered as:

- `subagent_<name>`

Example call pattern (internally by the model):

- Tool name: `subagent_doc_writer`
- Params: `{ "goal": "Write a migration guide for this repo" }`

## Custom Tools (Optional)

Beyond subagents, PAT supports Python tool discovery from:

- `<project>/.ai-agent/tools/*.py`
- `<system_config_dir>/ai-agent/tools/*.py`

Each file can define classes inheriting from the base `Tool` class. Discovered tools are auto-registered at session initialization.

## Persistence

PAT supports:

- Session snapshots (`/save`, `/sessions`, `/resume`)
- Checkpoints (`/checkpoint`, `/listcheckpoints`, `/restore`)
- Persistent user memory via the `memory` tool

## Security and Safety

- Credentials are stored in OS keyring (not plaintext config).
- Mutating operations can require confirmation depending on `approval` mode.
- Shell execution has blocked-pattern checks for dangerous commands.
- Shell environment can scrub secret-like variables via `exclude_patterns`.

## Troubleshooting

- If you see missing credential errors, run:
	- `pat-agent configure apikey <value>`
	- `pat-agent configure baseurl <value>`
- If MCP tools are missing, check `/mcp` output and server config.
- If a tool is not available, verify `allowed_tools` is not excluding it.

## Project Layout (High Level)

```text
Pat-Code/
	main.py                # CLI entrypoint
	agent/                 # agent loop + session runtime
	client/                # OpenAI-compatible client + stream parsing
	config/                # config model, loader, credentials
	context/               # message/context lifecycle and compaction
	tools/
		builtins/            # built-in tool implementations
		mcp/                 # MCP integration
		subagents.py         # subagent definitions/execution
	safety/                # approval policy and checks
	ui/                    # rich terminal UI
```

## License

MIT
