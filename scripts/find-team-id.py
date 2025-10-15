#!/usr/bin/env python3
"""
Find Slack Team ID from existing token
Works with both regular workspaces and Enterprise Grid orgs
"""

import json
from pathlib import Path

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except ImportError:
    print("ERROR: slack_sdk not installed")
    print("Install with: pip3 install slack-sdk")
    exit(1)

# Load token from MCP config
HOME = Path.home()
MCP_CONFIG = HOME / ".claude" / "mcp-servers.json"

print("=" * 60)
print("Slack Team ID Finder")
print("=" * 60)
print()

# Check if we have an existing config
existing_token = None
try:
    with open(MCP_CONFIG) as f:
        config = json.load(f)
        existing_token = config["mcpServers"]["slack"]["env"]["SLACK_BOT_TOKEN"]
        print(f"Found existing token in: {MCP_CONFIG}")
        print(f"  Token: {existing_token[:10]}...")
        print()
except (FileNotFoundError, KeyError):
    pass

# Prompt for token
print("Options:")
if existing_token:
    print("  1) Use existing token from config")
    print("  2) Enter a different token")
    print()
    choice = input("Choose [1/2]: ").strip()

    if choice == "1":
        token = existing_token
    elif choice == "2":
        token = input("Enter Slack token (xoxp-...): ").strip()
    else:
        print("Invalid choice")
        exit(1)
else:
    token = input("Enter Slack token (xoxp-...): ").strip()

if not token:
    print("ERROR: No token provided")
    exit(1)

print(f"Using token: {token[:10]}...")
print()

# Create Slack client
client = WebClient(token=token)

try:
    # Call auth.test to get workspace info
    response = client.auth_test()

    print("✓ Successfully authenticated!")
    print()
    print("Workspace Information:")
    print("-" * 60)
    print(f"  User:        {response.get('user')}")
    print(f"  User ID:     {response.get('user_id')}")
    print(f"  Team:        {response.get('team')}")
    print(f"  Team ID:     {response.get('team_id')} ⭐")
    print(f"  URL:         {response.get('url')}")

    if 'enterprise_id' in response:
        print(f"  Enterprise:  {response.get('enterprise_id')}")
        print()
        print("  Note: You're on Enterprise Grid!")
        print("  Use the Team ID (starts with T), not Enterprise ID (starts with E)")

    print()
    print("=" * 60)
    print("Configuration for new machine:")
    print("=" * 60)
    print()
    print("When running setup.sh on the new machine, use:")
    print(f'  Slack token:   {token[:15]}...')
    print(f'  Slack Team ID: {response.get("team_id")}')
    print()
    print("Or create a config.json with:")
    print(f'  "slack_token": "{token}",')
    print(f'  "slack_team_id": "{response.get("team_id")}"')
    print()

except SlackApiError as e:
    print(f"✗ ERROR: {e.response['error']}")
    print()

    if e.response['error'] == 'invalid_auth':
        print("Your token appears to be invalid or expired.")
        print("Generate a new token at: https://api.slack.com/apps")
    elif e.response['error'] == 'token_revoked':
        print("Your token has been revoked.")
        print("Generate a new token at: https://api.slack.com/apps")

    exit(1)

except Exception as e:
    print(f"✗ Unexpected error: {e}")
    exit(1)
