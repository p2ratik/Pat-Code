Right now, your built-in tools probably look like this:
ReadFileTool
WriteFileTool
ListDirectoryTool
RunCommandTool

Each inherits
class Tool:
    ...

The registry registers them, validates parameters, and exposes them to the LLM.

Keep that exactly as it is.

Don't create a separate "external tool architecture." Instead, extend the existing tool architecture.

Think in layers

Instead of

Built-in Tools

External Tools

MCP Tools
I'd think

                Tool
                  │
      ┌───────────┼────────────┐
      │           │            │
 Built-in     OAuth Tool    MCP Tool

Notice they're all still Tools.

The runtime shouldn't know the difference.

Separate authentication from execution

This is probably the most important design decision.

Many people end up writing something like

GoogleSheetsTool:
    authenticate()
    refresh_token()
    call_api()
    parse_response()

Then GitHub has another implementation.

Then Slack.

Then Drive.

Eventually every tool has 200 lines of OAuth code.

Don't do that.

Instead:
GoogleSheetsTool

↓

CredentialManager

↓

Google OAuth

↓

Google API

The tool should never care how authentication happened.

It should simply ask:

Give me a valid client.

For example

client = credential_manager.get_client(
    provider="google",
    user=user,
    scopes=[...]
)

Done.

Think of providers

Instead of thinking

Google Sheets Tool

Think

Google Provider

which knows

OAuth
Refresh tokens
Token expiry
Client construction

Then

Google Sheets Tool

Google Drive Tool

Google Calendar Tool

Gmail Tool

all reuse the same provider.

Likewise

GitHub Provider

↓

GitHub Tool

GitHub Issues Tool

GitHub PR Tool
I'd probably organize it something like
tools/

    base.py

    registry.py

    builtins/

        read_file.py
        write_file.py

    integrations/

        google/
            sheets.py
            drive.py
            calendar.py

        github/
            issues.py
            repo.py

        slack/
            send_message.py

Then another package

integrations/

    providers/

        google.py
        github.py
        slack.py

    oauth/

        credential_manager.py
        token_store.py
        oauth_flow.py

Notice tools don't own OAuth.

The execution flow becomes
LLM

↓

GoogleSheetsTool.execute()

↓

GoogleProvider.get_client(user)

↓

Credential Manager

↓

Refresh token if needed

↓

Return authenticated client

↓

Google Sheets API

The tool never knows if the token expired.

PAT already has something similar

Think about MCP.

Your runtime probably does something like

Tool

↓

MCP Connection

↓

MCP Server

The tool doesn't know

transport
authentication
sockets
HTTP

It simply invokes.

OAuth providers should feel exactly the same.

Another thing I'd add

Instead of exposing

Google Sheets

as one tool...

I'd expose operations.

For example

Google Sheets

↓

Read Sheet

Append Rows

Update Cells

Create Spreadsheet

List Sheets

Why?

Smaller tools have

clearer schemas
easier prompting
easier retries
easier verification

Instead of

GoogleSheetsTool

operation:
    read
    write
    update
    create

I'd rather have

ReadGoogleSheetTool

AppendRowsTool

UpdateCellsTool

The LLM is surprisingly good at selecting the right tool when each has a focused responsibility.

Credentials

You already designed tables for encrypted credentials.

I'd probably evolve them into

Provider

Google

GitHub

Slack

Dropbox

and

UserConnection

provider

user_id

encrypted_refresh_token

encrypted_access_token

expiry

metadata

The tools don't query the database.

The Credential Manager does.

I also wouldn't make Google Sheets "special"

From the runtime's perspective, every tool should satisfy the same contract:

Tool.execute(ctx, params)

Whether it's

ReadFileTool

or

ReadGoogleSheetTool

or

GitHubCreateIssueTool

the execution engine shouldn't branch based on tool type. The differences live behind the tool interface.

One last idea: think in terms of "capabilities"

Rather than asking, "How do I add Google Sheets?", ask, "How do I add a new provider with multiple capabilities?"

For example:

Google Provider
├── Sheets
│   ├── Read
│   ├── Append
│   └── Update
├── Drive
│   ├── Search
│   ├── Download
│   └── Upload
├── Calendar
│   ├── List Events
│   └── Create Event
└── Gmail
    ├── Read
    ├── Send
    └── Search

Once the Google Provider exists (OAuth, token refresh, client creation), adding a new Google capability becomes mostly an API wrapper plus a Tool subclass. The same pattern applies to GitHub, Slack, Microsoft 365, and others.