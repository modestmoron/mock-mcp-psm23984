# Mock MCP server (PSM-23984)

Fake MCP server (Streamable HTTP) used to reproduce a Workato MCP timeout. Returns two fake tools. No real data.

- `/close`: `tools/list` answered as SSE, stream closed after the answer
- `/open-silent`: answer sent, stream kept open with no more data
- `/open-ping`: answer sent, stream kept open with `: ping` every 5s

Start: `python mock_mcp_server.py` (listens on `$PORT`, default 8765)
