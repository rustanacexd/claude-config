# Exa MCP setup

API-key (stdio) setup:

```bash
claude mcp add exa -s user -e EXA_API_KEY=your_api_key -- npx -y exa-mcp-server
```

Hosted remote (HTTP) setup — the `tools` query param decides which tools the
endpoint exposes. Request all three sets so `web_fetch_exa` and the Exa Agent
(`agent_run`, from `agent_tools`) are available, not just search:

```bash
claude mcp add exa -s user --transport http \
  "https://mcp.exa.ai/mcp?exaApiKey=<key>&tools=web_search_exa,web_fetch_exa,agent_tools"
```

Omitting a tool from `tools` silently hides it — the server connects fine and
the missing tool simply never appears in the tool list.

After changing MCP configuration, restart Claude Code so the tool list is refreshed.
