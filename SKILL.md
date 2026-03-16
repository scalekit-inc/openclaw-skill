---
name: openclaw-tool-executor
description: |
  Use this skill whenever the user asks for information from, or wants to take an action in, a third-party tool or service. This includes — but is not limited to — searching the web, reading or writing documents, sending messages, querying databases, managing tasks, fetching data from APIs, or interacting with any connected SaaS product (e.g. "search Exa for...", "read my Notion page", "send a Slack message", "get my Google Sheet", "create a GitHub issue", "query Snowflake", "look up a HubSpot contact"). Trigger this skill any time the user's request involves an external service, integration, or data source — even if the provider is not explicitly named. Handles OAuth and non-OAuth (API Key, Bearer, Basic) connections, tool discovery, execution, and proxy fallback via Scalekit Connect.
homepage: https://github.com/scalekit-inc/openclaw-skill
metadata:
  openclaw:
    requires:
      bins: ["python3", "uv"]
      env:
        - TOOL_CLIENT_ID
        - TOOL_CLIENT_SECRET
        - TOOL_ENV_URL
        - TOOL_IDENTIFIER
    primaryEnv: TOOL_CLIENT_ID
    config:
      requiredEnv:
        - TOOL_CLIENT_ID
        - TOOL_CLIENT_SECRET
        - TOOL_ENV_URL
      example: |
        TOOL_CLIENT_ID=skc_your_client_id
        TOOL_CLIENT_SECRET=your_client_secret
        TOOL_ENV_URL=https://your-env.scalekit.cloud
        TOOL_IDENTIFIER=your_default_identifier
    install:
      - id: python-deps
        kind: exec
        command: "uv sync"
        label: "Install Python dependencies"
---

# OpenClaw Tool Executor

General-purpose tool executor for OpenClaw agents. Uses Scalekit Connect to discover and run tools for any connected service — OAuth (Notion, Slack, Gmail, GitHub, etc.) or non-OAuth (API Key, Bearer, Basic auth).

## Environment Variables

Required in `.env`:

```
TOOL_CLIENT_ID=<scalekit_client_id>
TOOL_CLIENT_SECRET=<scalekit_client_secret>
TOOL_ENV_URL=<scalekit_environment_url>
TOOL_IDENTIFIER=<default_identifier>   # optional but recommended
```

`TOOL_IDENTIFIER` is used as the default `--identifier` for all operations. If not set, the script will prompt the user at runtime and display a warning advising them to set it in `.env`.

## Execution Flow

When the user asks to perform an action on a connected service, follow these steps **in order**:

### Step 1 — Discover the Connection

Dynamically resolve the `connection_name` by listing all configured connections for the provider. The API paginates automatically through all pages:

```bash
uv run tool_exec.py --list-connections --provider <PROVIDER>
```

- Use the `key_id` from the first result as `<CONNECTION_NAME>` for all subsequent steps.
- If **no connection found** → inform the user that no `<PROVIDER>` connection is configured in Scalekit and stop.
- If **multiple connections found** → the first one is selected automatically (a warning is shown).

### Step 2 — Check & Authorize

Run `--generate-link` for the connection. The tool automatically detects the connection type (OAuth vs non-OAuth) and applies the correct auth flow:

```bash
uv run tool_exec.py --generate-link \
  --connection-name <CONNECTION_NAME>
```

**OAuth connections:**
- If already **ACTIVE** → proceed to Step 3.
- If **not active** → a magic link is generated. Present it to the user, wait for them to complete the flow, then proceed to Step 3.

**Non-OAuth connections (BEARER, BASIC, API Key, etc.):**
- If account **not found** → stop. Tell the user: *"Please create and configure the `<CONNECTION_NAME>` connection in the Scalekit Dashboard."*
- If account exists but **not active** → stop. Tell the user: *"Please activate the `<CONNECTION_NAME>` connection in the Scalekit Dashboard."*
- If **ACTIVE** → proceed to Step 3.

> Never use `--get-authorization` in the execution flow — that is only for inspecting raw OAuth tokens and does not work for non-OAuth connections.

### Step 3 — Discover Available Tools

Fetch the list of tools available for the provider:

```bash
uv run tool_exec.py --get-tool --provider <PROVIDER>
```

- Look for a tool that matches the user's intent (e.g. `notion_page_get` for reading a page).
- If a matching tool **exists** → go to Step 4.
- If **no matching tool exists** → go to Step 5 (proxy fallback).

You can also inspect a specific tool's schema:

```bash
uv run tool_exec.py --get-tool --tool-name <TOOL_NAME>
```

### Step 4 — Execute the Tool

Run the matched tool with the appropriate input:

```bash
uv run tool_exec.py --execute-tool \
  --tool-name <TOOL_NAME> \
  --connection-name <CONNECTION_NAME> \
  --tool-input '<JSON_INPUT>'
```

Return the result to the user.

### Step 5 — Proxy Fallback (only if no tool exists)

If no Scalekit tool covers the required action, attempt a proxied HTTP request directly to the provider's API:

```bash
uv run tool_exec.py --proxy-request \
  --connection-name <CONNECTION_NAME> \
  --path <API_PATH> \
  --method <GET|POST|PUT|DELETE> \
  --query-params '<JSON>' \   # optional
  --body '<JSON>'             # optional
```

> Note: Proxy may be disabled on some environments. If it returns `TOOL_PROXY_DISABLED`, inform the user that this action isn't supported by the current Scalekit tool catalog and suggest they request a new tool from Scalekit.

## Example: Search the web with Exa (API Key connection)

```
User: "Search for latest AI news using Exa"
```

1. `--list-connections --provider EXA` → `key_id: exa`, `type: API_KEY`
2. `--generate-link --connection-name exa` → detects API_KEY, checks account → ACTIVE
3. `--get-tool --provider EXA` → finds `exa_search`
4. `--execute-tool --tool-name exa_search --connection-name exa --tool-input '{"query": "latest AI news"}'`
   → returns search results

## Example: Read a Notion Page (OAuth connection)

```
User: "Read my Notion page https://notion.so/..."
```

1. `--list-connections --provider NOTION` → `key_id: notion-ijIQedmJ`, `type: OAUTH`
2. `--generate-link --connection-name notion-ijIQedmJ` → detects OAuth, already ACTIVE
3. `--get-tool --provider NOTION` → finds `notion_page_get`
4. `--execute-tool --tool-name notion_page_get --connection-name notion-ijIQedmJ --tool-input '{"page_id": "..."}'`
   → returns page metadata

## Example: Action Not Yet in Scalekit

```
User: "Fetch the blocks of a Notion page"
```

1. `--list-connections --provider NOTION` → `key_id: notion-ijIQedmJ`
2. `--generate-link --connection-name notion-ijIQedmJ` → ACTIVE
3. `--get-tool --provider NOTION` → no `notion_blocks_fetch` tool found
4. `--proxy-request --path "/blocks/<page_id>/children"` → fallback attempt
5. If proxy disabled → inform user the action isn't available yet

## Supported Providers

Any provider configured in Scalekit (Notion, Slack, Gmail, Google Sheets, GitHub, Salesforce, HubSpot, Linear, and 50+ more). Use the provider name in uppercase for `--provider` (e.g. `NOTION`, `SLACK`, `GOOGLE`).
