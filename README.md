# PAT Agent

PAT Agent is a smart command-line assistant that can help you work with files, run commands, search code, and automate repetitive tasks.

It is designed to be easy to use, even if you are not a programmer.

## Why People Use PAT

- It can read and edit files for you.
- It can run terminal commands safely.
- It can connect to external tools through MCP servers.
- It can run specialized mini-agents called subagents.
- It remembers context in a session so you can keep working naturally.

## 5-Minute Quick Demo

This section is for first-time users.

### 1) Install

```bash
pip install pat-agent 
```

After installation, the CLI command is:

```bash
pat-agent
```

### 2) Configure API Key and Base URL

```bash
pat-agent configure apikey YOUR_API_KEY
pat-agent configure baseurl YOUR_BASE_URL
```

Pat supports 3 Base urls :
1. Open router : https://openrouter.ai/api/v1
2. Openapi : https://api.openai.com/v1
3. Gemini : https://generativelanguage.googleapis.com/v1beta/openai/

Check what is configured:

```bash
pat-agent configure show
```

### 3) Start the Agent

```bash
pat-agent init 
pat-agent
```

You can now type plain English requests, for example:

- List all Python files in this project.
- Create a new README section for troubleshooting.
- Search for where session data is saved.

### 4) Run One Prompt and Exit (Optional)

```bash
pat-agent --prompt "Summarize this project in simple words"
```

## Screenshot / Demo Image

![PAT Demo](https://raw.githubusercontent.com/p2ratik/Pat-Code/master/Pat-Code/assets/image.png)


## Commands You Will Use Most

### Main Command

```bash
pat-agent [--prompt "..."] [--cwd PATH]
```

- `--prompt` or `-p`: run once and exit.
- `--cwd` or `-c`: run PAT in a specific folder.

### Configure Commands

```bash
pat-agent configure apikey VALUE
pat-agent configure baseurl VALUE
pat-agent configure show
pat-agent configure delete apikey
pat-agent configure delete baseurl
```

What each one does:

- `configure apikey`: saves your API key securely in OS keyring.
- `configure baseurl`: saves API endpoint URL securely in OS keyring.
- `configure show`: shows current configured values (API key is masked).
- `configure delete`: removes a saved value.

## Interactive Commands (Inside PAT)

When PAT is running, type these commands:

- `/help` : show help.
- `/clear` : clear current conversation.
- `/config` : show current active settings.
- `/model <name>` : switch model for this session.
- `/approval <policy>` : change safety approval mode.
- `/tools` : list available tools.
- `/mcp` : show MCP server status.
- `/stats` : show session stats.
- `/save` : save current session.
- `/sessions` : list saved sessions.
- `/resume <session_id>` : resume a saved session.
- `/checkpoint` : create a checkpoint.
- `/listcheckpoints` : list checkpoints.
- `/restore <checkpoint_id>` : restore a checkpoint.
- `/exit` or `/quit` : close PAT.

## Configuration System (Simple Explanation)

PAT loads settings from two places:

1. Global config on your machine.
2. Project config in your project folder.

Project config has higher priority.

### Config File Name

- `config.toml`

### Project Config Location

- `.ai-agent/config.toml` inside your project

### Example Config (Safe Starting Point)

```toml
max_turns = 100
approval = "on-request"

[model]
name = "elephant-alpha"
temperature = 1.0
context_window = 256000

[shell_environment]
ignore_default_excludes = false
exclude_patterns = ["*KEY*", "*TOKEN*", "*SECRET*"]
```

## How PAT Handles API Key and Base URL

PAT checks credentials in this order:

1. OS keyring (recommended)
2. Environment variables

Environment variable fallback names:

- `API_KEY`
- `BASE_URL`

## Tools, MCP, and Subagents

### Built-in Tools

PAT includes built-in tools for:

- File reading and writing
- File editing
- Directory listing
- Pattern search and glob search
- Shell commands
- Web search and web fetch
- Memory and todo tracking
- Multi-file patch application

### MCP Support

PAT can connect to MCP servers from config and auto-load their tools.

MCP tool names are registered in this format:

- `server_name__tool_name`

### Subagents

Subagents are focused mini-agents that PAT can call for specific tasks.

Default subagents:

- `subagent_codebase_investigator`
- `subagent_code_reviewer`

You can create your own subagents.

## Create Your Own Subagent

Add this to `.ai-agent/config.toml`:

```toml
[[user_subagents]]
name = "doc_writer"
description = "Writes and improves docs"
goal_prompt = "You are a documentation specialist. Write clear and beginner-friendly docs."
allowed_tools = ["read_file", "glob", "grep", "write_file", "edit"]
max_turns = 20
timeout_seconds = 600
```

Once loaded, the subagent appears as a tool named:

- `subagent_doc_writer`

## Approval Policies (Safety)

Available policies:

- `on-request`
- `on-failure`
- `auto`
- `auto-edit`
- `never`
- `yolo`

If you are new, start with:

- `on-request`

## Plain-Language Architecture

PAT follows a simple flow:

1. You ask something.
2. PAT sends your request + context to the model.
3. The model decides if tools are needed.
4. PAT runs tools (with approval checks if needed).
5. PAT returns the final response.

This loop continues until the task is done.

## Troubleshooting

- If PAT says API key is missing, run:
  - `pat-agent configure apikey YOUR_API_KEY`
- If PAT cannot reach your provider, check base URL:
  - `pat-agent configure baseurl YOUR_BASE_URL`
- If tools are missing, run `/tools` and verify your config is not restricting them.
- If MCP tools are missing, run `/mcp` and check MCP server config.

## Project Structure (High Level)

```text
Pat-Code/
  main.py
  agent/
  client/
  config/
  context/
  tools/
  safety/
  ui/
```

## License

MIT
