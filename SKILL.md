---
name: openclaw-tool-executor
description: General-purpose tool executor for OpenClaw agents. Triggers when the user asks to perform an action using a connected third-party service (e.g. "read my Notion page", "send a Slack message", "query my Google Sheet"). Handles OAuth authorization, tool discovery, execution, and proxy fallback via Scalekit Connect.
homepage: https://github.com/Avinash-Kamath/openclaw-skill
metadata:
  openclaw:
    requires:
      bins: ["python3", "uv"]
    install:
      - id: python-deps
        kind: exec
        command: "uv sync"
        label: "Install Python dependencies"
---

# OpenClaw Tool Executor

General-purpose tool executor for OpenClaw agents. Uses Scalekit Connect to discover and run tools for any connected OAuth service (Notion, Slack, Gmail, GitHub, etc.).

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

Run `--generate-link` for every connection type (OAuth, BASIC, or any other). Scalekit handles all auth types uniformly — it checks the account status and only presents a magic link if authorization is needed:

```bash
uv run tool_exec.py --generate-link \
  --connection-name <CONNECTION_NAME>
```

- If the account is already **ACTIVE** → Scalekit reports it as connected, proceed to Step 3.
- If **not active** → Scalekit generates a magic link. Present it to the user, wait for them to complete the flow, then proceed to Step 3.

> Never use `--get-authorization` in the execution flow — that is only for inspecting raw OAuth tokens and does not work for BASIC auth connections.

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

## Example: Read a Notion Page

```
User: "Read my Notion page https://notion.so/..."
```

1. `--list-connections --provider NOTION` → `key_id: notion-ijIQedmJ`
2. `--generate-link --connection-name notion-ijIQedmJ` → already ACTIVE, no link needed
3. `--get-tool --provider NOTION` → finds `notion_page_get`
4. `--execute-tool --tool-name notion_page_get --tool-input '{"page_id": "..."}'`
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
