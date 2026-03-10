#!/usr/bin/env python3
"""
Scalekit Connect CLI

Command-line tool for testing Scalekit tool execution via the Connect SDK.
Supports generating authorization links, executing tools, and fetching tool metadata.

Usage:
    python connect.py --generate-link --connection-name SLACK --identifier user_123
    python connect.py --execute-tool --tool-name slack_send_message --connection-name SLACK --identifier user_123 --tool-input '{"channel": "#general", "text": "Hello!"}'
    python connect.py --get-tool --tool-name googlesheets_get_values
    python connect.py --get-tool --provider GOOGLE --page-size 5

Required environment variables:
    TOOL_CLIENT_ID      - Scalekit OAuth client ID
    TOOL_CLIENT_SECRET  - Scalekit OAuth client secret
    TOOL_ENV_URL        - Scalekit environment URL (e.g. https://your-env.scalekit.cloud)
"""

import argparse
import json
import mimetypes
import os
import sys

import requests
from google.protobuf.json_format import MessageToDict

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import scalekit.client as scalekit_sdk

# ANSI colors
BOLD = '\033[1m'
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

# Environment variables
TOOL_CLIENT_ID = os.getenv('TOOL_CLIENT_ID', '')
TOOL_CLIENT_SECRET = os.getenv('TOOL_CLIENT_SECRET', '')
TOOL_ENV_URL = os.getenv('TOOL_ENV_URL', '')
TOOL_IDENTIFIER = os.getenv('TOOL_IDENTIFIER', '')


def get_connect_client():
    """Initialize and return the Scalekit connect client."""
    client = scalekit_sdk.ScalekitClient(
        TOOL_ENV_URL,
        TOOL_CLIENT_ID,
        TOOL_CLIENT_SECRET
    )
    return client.connect


def get_scalekit_client():
    """Initialize and return the full Scalekit client."""
    return scalekit_sdk.ScalekitClient(
        TOOL_ENV_URL,
        TOOL_CLIENT_ID,
        TOOL_CLIENT_SECRET
    )


def generate_link(connection_name: str, identifier: str) -> None:
    """
    Get or create a connected account and generate an authorization link if not active.
    If already active, reports the connection status.
    """
    connect = get_connect_client()

    print(f"   Connection: {connection_name}")
    print(f"   Identifier: {identifier}")
    print()

    try:
        response = connect.get_or_create_connected_account(
            connection_name=connection_name,
            identifier=identifier
        )
        connected_account = response.connected_account

        print(f"   Connected Account ID: {connected_account.id}")
        print(f"   Status: {connected_account.status}")

        if connected_account.status != "ACTIVE":
            print(f"\n{YELLOW}⚠️  {connection_name} is not connected (status: {connected_account.status}){RESET}")

            link_response = connect.get_authorization_link(
                connection_name=connection_name,
                identifier=identifier
            )

            print(f"\n🔗 Click the link to authorize {connection_name}:")
            print(f"   {BLUE}{link_response.link}{RESET}")
            print()

            try:
                input(f"⎆ Press Enter after authorizing {connection_name}...")
                print(f"\n{GREEN}✅ Done! You can now execute tools for {connection_name}.{RESET}")
            except (KeyboardInterrupt, EOFError):
                print(f"\n{YELLOW}(Non-interactive mode — authorize the link above, then re-run to continue.){RESET}")
                sys.exit(0)
        else:
            print(f"\n{GREEN}✅ {connection_name} is already connected and active!{RESET}")

    except Exception as e:
        print(f"\n{RED}❌ Error: {e}{RESET}")
        sys.exit(1)


def execute_tool(tool_name: str, connection_name: str, identifier: str, tool_input: dict) -> None:
    """
    Get or create a connected account, prompt for authorization if not active,
    then execute the specified tool.
    """
    connect = get_connect_client()

    print(f"   Tool: {tool_name}")
    print(f"   Connection: {connection_name}")
    print(f"   Identifier: {identifier}")
    print(f"   Input: {json.dumps(tool_input, indent=2)}")
    print()

    try:
        response = connect.get_or_create_connected_account(
            connection_name=connection_name,
            identifier=identifier
        )
        connected_account = response.connected_account

        print(f"   Connected Account ID: {connected_account.id}")
        print(f"   Status: {connected_account.status}")

        if connected_account.status != "ACTIVE":
            print(f"\n{YELLOW}⚠️  {connection_name} is not connected (status: {connected_account.status}){RESET}")

            link_response = connect.get_authorization_link(
                connection_name=connection_name,
                identifier=identifier
            )

            print(f"\n🔗 Click the link to authorize {connection_name}:")
            print(f"   {BLUE}{link_response.link}{RESET}")
            print()

            try:
                input(f"⎆ Press Enter after authorizing {connection_name}...")
            except (KeyboardInterrupt, EOFError):
                print(f"\n{YELLOW}(Non-interactive mode — authorize the link above, then re-run to execute.){RESET}")
                sys.exit(0)

            # Re-fetch connected account after authorization
            response = connect.get_or_create_connected_account(
                connection_name=connection_name,
                identifier=identifier
            )
            connected_account = response.connected_account

        print(f"\n🔧 Executing tool: {BOLD}{tool_name}{RESET}")

        result = connect.execute_tool(
            tool_name=tool_name,
            identifier=identifier,
            connected_account_id=connected_account.id,
            tool_input=tool_input
        )

        print(f"\n{GREEN}✅ Result:{RESET}")
        if isinstance(result, (dict, list)):
            print(json.dumps(result, indent=2))
        else:
            print(result)

    except Exception as e:
        print(f"\n{RED}❌ Error: {e}{RESET}")
        sys.exit(1)


def proxy_request(
        connection_name: str,
        identifier: str,
        path: str,
        method: str = "GET",
        query_params: dict = None,
        body: dict = None,
        output_file: str = None,
        input_file: str = None,
) -> None:
    """
    Make a proxied HTTP request through Scalekit on behalf of a connected account.
    Handles binary responses (files, exports) that gRPC-based execute_tool cannot.
    """
    client = get_scalekit_client()

    print(f"   Connection: {connection_name}")
    print(f"   Identifier: {identifier}")
    print(f"   Method: {method.upper()}")
    print(f"   Path: {path}")
    if query_params:
        print(f"   Query Params: {json.dumps(query_params, indent=2)}")
    if body:
        print(f"   Body: {json.dumps(body, indent=2)}")
    if input_file:
        print(f"   Input File: {input_file}")
    print()

    try:
        if input_file:
            with open(input_file, "rb") as f:
                file_bytes = f.read()
            file_mime = mimetypes.guess_type(input_file)[0] or "application/octet-stream"
            print(f"   File size: {len(file_bytes):,} bytes")
            print(f"   File MIME: {file_mime}")
            print()

        response = client.actions.request(
            connection_name=connection_name,
            identifier=identifier,
            path=path,
            method=method,
            query_params=query_params or {},
            body=body,
            form_data=file_bytes if input_file else None,
            headers={"Content-Type": file_mime} if input_file else None,
        )

        content_type = response.headers.get("Content-Type", "")
        print(f"   Status: {response.status_code}")
        print(f"   Content-Type: {content_type}")
        print()

        if response.status_code >= 400:
            print(f"{RED}❌ Error response:{RESET}")
            try:
                print(json.dumps(response.json(), indent=2))
            except Exception:
                print(response.text)
            sys.exit(1)

        # Save to file if requested
        if output_file:
            with open(output_file, "wb") as f:
                f.write(response.content)
            print(f"{GREEN}✅ Saved {len(response.content):,} bytes to: {output_file}{RESET}")
            return

        # JSON response — pretty print
        if "application/json" in content_type:
            print(f"{GREEN}✅ Result:{RESET}")
            print(json.dumps(response.json(), indent=2))
        # Text response — print directly
        elif content_type.startswith("text/"):
            print(f"{GREEN}✅ Result ({len(response.text):,} chars):{RESET}")
            print(response.text[:3000])
            if len(response.text) > 3000:
                print(f"\n{YELLOW}... (truncated, {len(response.text):,} total chars){RESET}")
        # Binary — show info and base64 snippet
        else:
            import base64
            encoded = base64.b64encode(response.content).decode("utf-8")
            print(f"{GREEN}✅ Binary response ({len(response.content):,} bytes){RESET}")
            print(f"   Base64 preview: {encoded[:100]}...")
            print(f"\n{YELLOW}Tip: use --output-file <path> to save the file.{RESET}")

    except Exception as e:
        print(f"\n{RED}❌ Error: {e}{RESET}")
        sys.exit(1)


def get_authorization(connection_name: str, identifier: str) -> None:
    """
    Fetch the connected account and display OAuth access and refresh tokens.
    """
    client = get_scalekit_client()

    print(f"   Connection: {connection_name}")
    print(f"   Identifier: {identifier}")
    print()

    try:
        response = client.actions.get_connected_account(
            connection_name=connection_name,
            identifier=identifier,
        )
        connected_account = response.connected_account

        print(f"   Connected Account ID: {connected_account.id}")
        print(f"   Status: {connected_account.status}")
        print()

        tokens = connected_account.authorization_details["oauth_token"]
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        print(f"{GREEN}✅ Tokens retrieved:{RESET}")
        print(f"   Access Token:  {access_token}")
        print(f"   Refresh Token: {refresh_token}")

    except KeyError as e:
        print(f"{RED}❌ Error: Could not find token key {e}. authorization_details: {connected_account.authorization_details}{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}❌ Error: {e}{RESET}")
        sys.exit(1)


def get_bearer_token() -> str:
    """
    Obtain a management API bearer token via OAuth2 client credentials grant.
    """
    token_url = f"{TOOL_ENV_URL.rstrip('/')}/oauth/token"
    response = requests.post(token_url, data={
        "grant_type": "client_credentials",
        "client_id": TOOL_CLIENT_ID,
        "client_secret": TOOL_CLIENT_SECRET,
    })
    response.raise_for_status()
    return response.json()["access_token"]


def list_connections(provider: str = None, page_size: int = 20) -> None:
    """
    List all configured connections for this environment, paginating through all pages.
    Optionally filter by provider_key (e.g. NOTION, SLACK).
    Prints each connection's key_id (used as --connection-name) and status.
    """
    try:
        token = get_bearer_token()
    except Exception as e:
        print(f"\n{RED}❌ Failed to get bearer token: {e}{RESET}")
        sys.exit(1)

    url = f"{TOOL_ENV_URL.rstrip('/')}/api/v1/connections/app"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    all_connections = []
    page_token = ""

    while True:
        try:
            response = requests.get(url, params={"page_size": page_size, "page_token": page_token}, headers=headers)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"\n{RED}❌ Error fetching connections: {e}{RESET}")
            sys.exit(1)

        all_connections.extend(data.get("connections", []))

        next_page_token = data.get("next_page_token", "")
        if not next_page_token:
            break
        page_token = next_page_token

    connections = all_connections
    if provider:
        connections = [c for c in connections if c.get("provider_key", "").upper() == provider.upper()]

    if not connections:
        print(f"{YELLOW}No connections found{' for provider ' + provider if provider else ''}.{RESET}")
        return

    if provider and len(connections) > 1:
        print(f"{YELLOW}⚠️  Multiple connections found for {provider}, using the first one: {connections[0]['key_id']}{RESET}\n")
        connections = [connections[0]]

    print(json.dumps(connections, indent=2))


def get_tool(tool_name: str = None, provider: str = None, page_size: int = None, page_token: str = None) -> None:
    """
    Fetch tool metadata from the Scalekit tools API and print as JSON.
    """
    client = get_scalekit_client()

    try:
        from scalekit.v1.tools.tools_pb2 import Filter

        filter_kwargs = {}
        if tool_name:
            filter_kwargs['tool_name'] = [tool_name]
        if provider:
            filter_kwargs['provider'] = provider

        list_kwargs = {}
        if filter_kwargs:
            list_kwargs['filter'] = Filter(**filter_kwargs)
        if page_size is not None:
            list_kwargs['page_size'] = page_size
        if page_token:
            list_kwargs['page_token'] = page_token

        response, _ = client.tools.list_tools(**list_kwargs)
        result = MessageToDict(response, preserving_proto_field_name=True)
        print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"\n{RED}❌ Error: {e}{RESET}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Scalekit Connect CLI - Generate auth links, execute tools, and fetch tool metadata',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate authorization link for a connection
  python connect.py --generate-link --connection-name SLACK --identifier user_123

  # Execute a tool (will prompt for auth if not connected)
  python connect.py --execute-tool --tool-name slack_send_message \\
      --connection-name SLACK --identifier user_123 \\
      --tool-input '{"channel": "#general", "text": "Hello!"}'

  # Fetch tool metadata by name
  python connect.py --get-tool --tool-name googlesheets_get_values

  # Fetch tools by provider with pagination
  python connect.py --get-tool --provider GOOGLE --page-size 5
  python connect.py --get-tool --page-size 5 --page-token <token>

Required environment variables:
  TOOL_CLIENT_ID      Scalekit OAuth client ID
  TOOL_CLIENT_SECRET  Scalekit OAuth client secret
  TOOL_ENV_URL        Scalekit environment URL
        """
    )

    # Operation flags (mutually exclusive)
    operation_group = parser.add_mutually_exclusive_group(required=True)
    operation_group.add_argument(
        '--generate-link',
        action='store_true',
        help='Get or create a connected account and generate an authorization link if not active'
    )
    operation_group.add_argument(
        '--execute-tool',
        action='store_true',
        help='Execute a tool on behalf of a user (prompts for auth if not connected)'
    )
    operation_group.add_argument(
        '--get-tool',
        action='store_true',
        help='Fetch tool metadata from the Scalekit tools API and print as JSON'
    )
    operation_group.add_argument(
        '--proxy-request',
        action='store_true',
        help='Make a proxied HTTP request through Scalekit (handles binary file responses)'
    )
    operation_group.add_argument(
        '--get-authorization',
        action='store_true',
        help='Fetch OAuth access and refresh tokens for a connected account'
    )
    operation_group.add_argument(
        '--list-connections',
        action='store_true',
        help='List all configured connections for this environment. Optionally filter by --provider.'
    )

    # Shared arguments for --generate-link and --execute-tool
    parser.add_argument(
        '--connection-name',
        help='Name of the connection (e.g. SLACK, GMAIL) — required for --generate-link and --execute-tool'
    )
    parser.add_argument(
        '--identifier',
        default=TOOL_IDENTIFIER or None,
        help='Unique identifier for the connected account — required for --generate-link and --execute-tool. Defaults to TOOL_IDENTIFIER env var.'
    )

    # Arguments for --execute-tool
    parser.add_argument(
        '--tool-name',
        help='Name of the tool to execute or fetch (required for --execute-tool, optional for --get-tool)'
    )
    parser.add_argument(
        '--tool-input',
        help='JSON string of tool input parameters (required for --execute-tool)'
    )

    # Arguments for --proxy-request
    parser.add_argument(
        '--path',
        help='API path to proxy (e.g. /drive/v3/files/FILE_ID/export) — required for --proxy-request'
    )
    parser.add_argument(
        '--method',
        default='GET',
        help='HTTP method for --proxy-request (default: GET)'
    )
    parser.add_argument(
        '--query-params',
        help='JSON string of query parameters for --proxy-request (e.g. \'{"mimeType": "text/plain"}\')'
    )
    parser.add_argument(
        '--body',
        help='JSON string of request body for --proxy-request'
    )
    parser.add_argument(
        '--output-file',
        help='Save binary response to this file path (used with --proxy-request)'
    )
    parser.add_argument(
        '--input-file',
        help='Path to a file to upload as the request body (used with --proxy-request)'
    )

    # Arguments for --get-tool
    parser.add_argument(
        '--provider',
        help='Filter tools by provider (e.g. GOOGLE, SLACK) — used with --get-tool'
    )
    parser.add_argument(
        '--page-size',
        type=int,
        help='Number of tools per page (used with --get-tool, default: API default)'
    )
    parser.add_argument(
        '--page-token',
        help='Pagination token from a previous --get-tool response'
    )

    args = parser.parse_args()

    # Validate environment variables
    if not TOOL_CLIENT_ID:
        print(f"{RED}❌ Error: TOOL_CLIENT_ID environment variable is required{RESET}")
        sys.exit(1)
    if not TOOL_CLIENT_SECRET:
        print(f"{RED}❌ Error: TOOL_CLIENT_SECRET environment variable is required{RESET}")
        sys.exit(1)
    if not TOOL_ENV_URL:
        print(f"{RED}❌ Error: TOOL_ENV_URL environment variable is required{RESET}")
        sys.exit(1)

    # Resolve identifier: env var → CLI arg → prompt user
    if not args.identifier:
        if not TOOL_IDENTIFIER:
            print(f"{YELLOW}⚠️  Warning: TOOL_IDENTIFIER is not set in your .env config.{RESET}")
            print(f"   Add TOOL_IDENTIFIER=<your_identifier> to .env to avoid this prompt.")
            print()
            try:
                args.identifier = input("Enter identifier: ").strip()
            except (KeyboardInterrupt, EOFError):
                print(f"\n{RED}❌ Identifier is required. Set TOOL_IDENTIFIER in .env or pass --identifier.{RESET}")
                sys.exit(1)
            if not args.identifier:
                print(f"{RED}❌ Identifier cannot be empty.{RESET}")
                sys.exit(1)
        else:
            args.identifier = TOOL_IDENTIFIER

    print(f"🚀 Scalekit Connect CLI")
    print(f"   Env URL: {TOOL_ENV_URL}")
    print(f"   Client ID: {TOOL_CLIENT_ID[:8]}...")

    if args.generate_link:
        print(f"   Operation: Generate Auth Link")
        print()

        if not args.connection_name:
            print(f"{RED}❌ Error: --connection-name is required for --generate-link{RESET}")
            sys.exit(1)
        if not args.identifier:
            print(f"{RED}❌ Error: --identifier is required for --generate-link{RESET}")
            sys.exit(1)

        generate_link(
            connection_name=args.connection_name,
            identifier=args.identifier
        )

    elif args.execute_tool:
        print(f"   Operation: Execute Tool")
        print()

        if not args.connection_name:
            print(f"{RED}❌ Error: --connection-name is required for --execute-tool{RESET}")
            sys.exit(1)
        if not args.identifier:
            print(f"{RED}❌ Error: --identifier is required for --execute-tool{RESET}")
            sys.exit(1)
        if not args.tool_name:
            print(f"{RED}❌ Error: --tool-name is required for --execute-tool{RESET}")
            sys.exit(1)
        if not args.tool_input:
            print(f"{RED}❌ Error: --tool-input is required for --execute-tool{RESET}")
            sys.exit(1)

        try:
            tool_input = json.loads(args.tool_input)
        except json.JSONDecodeError as e:
            print(f"{RED}❌ Error: --tool-input is not valid JSON: {e}{RESET}")
            sys.exit(1)

        execute_tool(
            tool_name=args.tool_name,
            connection_name=args.connection_name,
            identifier=args.identifier,
            tool_input=tool_input
        )

    elif args.proxy_request:
        print(f"   Operation: Proxy Request")
        print()

        if not args.connection_name:
            print(f"{RED}❌ Error: --connection-name is required for --proxy-request{RESET}")
            sys.exit(1)
        if not args.identifier:
            print(f"{RED}❌ Error: --identifier is required for --proxy-request{RESET}")
            sys.exit(1)
        if not args.path:
            print(f"{RED}❌ Error: --path is required for --proxy-request{RESET}")
            sys.exit(1)

        query_params = None
        if args.query_params:
            try:
                query_params = json.loads(args.query_params)
            except json.JSONDecodeError as e:
                print(f"{RED}❌ Error: --query-params is not valid JSON: {e}{RESET}")
                sys.exit(1)

        body = None
        if args.body:
            try:
                body = json.loads(args.body)
            except json.JSONDecodeError as e:
                print(f"{RED}❌ Error: --body is not valid JSON: {e}{RESET}")
                sys.exit(1)

        proxy_request(
            connection_name=args.connection_name,
            identifier=args.identifier,
            path=args.path,
            method=args.method,
            query_params=query_params,
            body=body,
            output_file=args.output_file,
            input_file=args.input_file,
        )

    elif args.get_authorization:
        print(f"   Operation: Get Authorization")
        print()

        if not args.connection_name:
            print(f"{RED}❌ Error: --connection-name is required for --get-authorization{RESET}")
            sys.exit(1)
        if not args.identifier:
            print(f"{RED}❌ Error: --identifier is required for --get-authorization{RESET}")
            sys.exit(1)

        get_authorization(
            connection_name=args.connection_name,
            identifier=args.identifier,
        )

    elif args.get_tool:
        print(f"   Operation: Get Tool")
        print()

        get_tool(
            tool_name=args.tool_name,
            provider=args.provider,
            page_size=args.page_size,
            page_token=args.page_token,
        )

    elif args.list_connections:
        print(f"   Operation: List Connections")
        print()

        list_connections(
            provider=args.provider,
            page_size=args.page_size or 20,
        )


if __name__ == '__main__':
    main()
