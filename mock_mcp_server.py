#!/usr/bin/env python3
"""Mock MCP server (Streamable HTTP) for PSM-23984.

Paths (all POST, JSON-RPC):
  /close       tools/list answered as SSE, stream closed right after the answer (normal)
  /open-silent tools/list answered as SSE, then the stream stays open with no more data
  /open-ping   tools/list answered as SSE, then the stream stays open and sends ": ping" every 5s

initialize        -> plain JSON + Mcp-Session-Id header
notifications/*   -> 202 Accepted
"""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOOLS = [
    {"name": "find_company", "description": "Find a company by domain",
     "inputSchema": {"type": "object", "properties": {"domain": {"type": "string"}}}},
    {"name": "get_intent_score", "description": "Get account intent score",
     "inputSchema": {"type": "object", "properties": {"account_id": {"type": "string"}}}},
]
HOLD_SECONDS = 120


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def _chunk(self, text):
        data = text.encode()
        self.wfile.write(f"{len(data):X}\r\n".encode() + data + b"\r\n")
        self.wfile.flush()

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0)
        msg = json.loads(body or b"{}")
        method, req_id, mode = msg.get("method"), msg.get("id"), self.path.rstrip("/")
        log(f"{mode} <- {method} (id={req_id})")

        if method == "initialize":
            out = json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {
                "protocolVersion": msg.get("params", {}).get("protocolVersion", "2025-03-26"),
                "capabilities": {"tools": {}}, "serverInfo": {"name": "mock-6sense", "version": "1.0"}}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Mcp-Session-Id", "mock-session-1")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            return

        if method is None or method.startswith("notifications/"):
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if method == "tools/list":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            answer = json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}})
            self._chunk(f"event: message\ndata: {answer}\n\n")
            log(f"{mode} -> sent tools/list answer")
            try:
                if mode == "/close":
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
                    log(f"{mode} -> stream closed")
                elif mode == "/open-ping":
                    for _ in range(HOLD_SECONDS // 5):
                        time.sleep(5)
                        self._chunk(": ping\n\n")
                    log(f"{mode} -> gave up holding")
                else:
                    time.sleep(HOLD_SECONDS)
                    log(f"{mode} -> gave up holding")
            except (BrokenPipeError, ConnectionResetError):
                log(f"{mode} -> client disconnected")
            self.close_connection = True
            return

        self.send_response(400)
        self.send_header("Content-Length", "0")
        self.end_headers()


if __name__ == "__main__":
    port = int(os.environ.get("PORT") or (sys.argv[1] if len(sys.argv) > 1 else 8765))
    log(f"mock MCP server on 0.0.0.0:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
