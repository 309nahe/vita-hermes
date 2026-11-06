#!/usr/bin/env python3
"""Mock Hermes Agent API server for developing the Vita client without a real agent.

Speaks the OpenAI-compatible subset the client needs:
  GET  /health
  GET  /v1/models
  POST /v1/chat/completions   (stream true -> SSE, false -> JSON)

Standard library only. Examples:
  tools/mock_hermes.py                         # http://127.0.0.1:8642, no auth
  tools/mock_hermes.py --token s3cretToken1234 # require Authorization: Bearer ...
  tools/mock_hermes.py --replay docs/samples/real.sse --delay 0.05
  tools/mock_hermes.py --fault drop            # cut the stream mid-reply
Faults: none | unauthorized | server-error | slow | drop | stall | bad-json
"""
import argparse, json, sys, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_REPLY = (
    "Hello from the mock Hermes server.\n\n"
    "# Markdown test\n"
    "Some **bold**, some *italic* and `inline code`.\n\n"
    "- first item\n- second item\n\n"
    "```python\nprint('hello vita')\n```\n\n"
    "You said: {echo}"
)

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    args = None  # set in main()

    def log_message(self, fmt, *a):
        sys.stderr.write("[mock] %s %s\n" % (self.address_string(), fmt % a))

    # -- helpers
    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        if self.args.fault == "unauthorized":
            return False
        if not self.args.token:
            return True
        return self.headers.get("Authorization", "") == "Bearer " + self.args.token

    def _check(self):
        if not self._authorized():
            self._json(401, {"error": {"message": "invalid api key", "type": "auth"}})
            return False
        if self.args.fault == "server-error":
            self._json(500, {"error": {"message": "mock server error"}})
            return False
        return True

    # -- routes
    def do_GET(self):
        if self.path == "/health":
            return self._json(200, {"status": "ok"})
        if not self._check():
            return
        if self.path.rstrip("/") == "/v1/models":
            return self._json(200, {"object": "list", "data": [
                {"id": "hermes-agent", "object": "model", "owned_by": "mock"}]})
        self._json(404, {"error": {"message": "not found"}})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        if not self._check():
            return
        if self.path.rstrip("/") != "/v1/chat/completions":
            return self._json(404, {"error": {"message": "not found"}})
        try:
            req = json.loads(raw)
        except ValueError:
            return self._json(400, {"error": {"message": "bad json"}})
        msgs = req.get("messages") or []
        last = next((m.get("content", "") for m in reversed(msgs) if m.get("role") == "user"), "")
        if isinstance(last, list):  # content parts
            last = " ".join(p.get("text", "") for p in last if isinstance(p, dict))
        self.log_message("chat: %d msgs, stream=%s, last=%r", len(msgs), req.get("stream"), last[:60])
        text = DEFAULT_REPLY.format(echo=last)
        cid = "chatcmpl-" + uuid.uuid4().hex[:12]
        model = req.get("model", "hermes-agent")
        if not req.get("stream"):
            return self._json(200, {
                "id": cid, "object": "chat.completion", "created": int(time.time()), "model": model,
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": text}}]})
        self._stream(cid, model, text)

    def _send_chunk(self, data: bytes):
        # HTTP/1.1 chunked transfer
        self.wfile.write(b"%x\r\n" % len(data) + data + b"\r\n")
        self.wfile.flush()

    def _event(self, obj):
        self._send_chunk(b"data: " + (obj if isinstance(obj, bytes) else json.dumps(obj).encode()) + b"\n\n")

    def _stream(self, cid, model, text):
        a = self.args
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        try:
            if a.replay:
                with open(a.replay, "rb") as f:
                    for block in f.read().split(b"\n\n"):
                        if block.strip():
                            self._send_chunk(block + b"\n\n")
                            time.sleep(a.delay)
                self._send_chunk(b"")  # terminate chunked body
                return
            def chunk(delta, finish=None):
                return {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                        "model": model, "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
            self._event(chunk({"role": "assistant"}))
            pieces = [text[i:i + a.chunk] for i in range(0, len(text), a.chunk)]
            for i, p in enumerate(pieces):
                if a.fault == "drop" and i == len(pieces) // 2:
                    self.connection.close()   # simulate Wi-Fi drop mid-stream
                    return
                if a.fault == "stall" and i == len(pieces) // 2:
                    time.sleep(3600)
                if a.fault == "bad-json" and i == 2:
                    self._event(b"{not json")
                self._event(chunk({"content": p}))
                time.sleep(a.delay * (10 if a.fault == "slow" else 1))
            self._event(chunk({}, "stop"))
            self._event(b"[DONE]")
            self._send_chunk(b"")
        except (BrokenPipeError, ConnectionResetError):
            self.log_message("client disconnected mid-stream")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8642)
    ap.add_argument("--token", default="", help="require this bearer token (empty = no auth)")
    ap.add_argument("--delay", type=float, default=0.03, help="seconds between chunks")
    ap.add_argument("--chunk", type=int, default=6, help="characters per chunk")
    ap.add_argument("--replay", help="file with a raw recorded SSE stream to replay")
    ap.add_argument("--fault", default="none",
                    choices=["none", "unauthorized", "server-error", "slow", "drop", "stall", "bad-json"])
    Handler.args = ap.parse_args()
    a = Handler.args
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"mock hermes on http://{a.host}:{a.port}/v1  token={'set' if a.token else 'none'} fault={a.fault}",
          file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
