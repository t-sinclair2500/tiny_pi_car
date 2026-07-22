#!/usr/bin/env python3
"""Tiny OpenAI-compatible translator in front of LM Studio.

LM Studio often returns ``"tool_calls": []`` on every completion. Some OpenCode
builds hang forever treating that as pending tool use. This proxy strips empty
``tool_calls`` (and empty ``function_call``) from JSON + SSE responses while
leaving real tool calls untouched.

Usage:
  python3 scripts/lms_openai_proxy.py
  # point OpenCode lm-studio baseURL at http://127.0.0.1:1240/v1
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


def _strip_empty_tools(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {k: _strip_empty_tools(v) for k, v in obj.items()}
        if out.get("tool_calls") == []:
            out.pop("tool_calls", None)
        if out.get("function_call") == {}:
            out.pop("function_call", None)
        # Some clients also choke on explicit null tool_calls.
        if out.get("tool_calls") is None and "tool_calls" in out:
            out.pop("tool_calls", None)
        return out
    if isinstance(obj, list):
        return [_strip_empty_tools(item) for item in obj]
    return obj


def _transform_json_bytes(payload: bytes) -> bytes:
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return payload
    return json.dumps(_strip_empty_tools(data), ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def _transform_sse_line(line: str) -> str:
    if not line.startswith("data: "):
        return line
    raw = line[6:]
    if raw.strip() in {"", "[DONE]"}:
        return line
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return line
    return "data: " + json.dumps(
        _strip_empty_tools(data), ensure_ascii=False, separators=(",", ":")
    )


class ProxyHandler(BaseHTTPRequestHandler):
    upstream_base: str = "http://127.0.0.1:1234"
    timeout_s: float = 600.0
    verbose: bool = True
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("[lms-proxy] " + (fmt % args) + "\n")

    def _vlog(self, msg: str) -> None:
        if self.verbose:
            sys.stderr.write(f"[lms-proxy] {msg}\n")
            sys.stderr.flush()

    def _forward(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length > 0 else None
        url = self.upstream_base.rstrip("/") + self.path
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower()
            not in {
                "host",
                "content-length",
                "connection",
                "transfer-encoding",
                "accept-encoding",
            }
        }
        if body is not None:
            headers["Content-Length"] = str(len(body))
            try:
                req_json = json.loads(body.decode("utf-8"))
                self._vlog(
                    f"REQ {self.command} {self.path} stream={req_json.get('stream')} "
                    f"model={req_json.get('model')} "
                    f"max_tokens={req_json.get('max_tokens') or req_json.get('max_completion_tokens')} "
                    f"tools={len(req_json.get('tools') or [])} "
                    f"msgs={len(req_json.get('messages') or [])}"
                )
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                self._vlog(f"REQ {self.command} {self.path} body_bytes={len(body)}")

        request = urllib.request.Request(
            url,
            data=body if self.command != "GET" else None,
            headers=headers,
            method=self.command,
        )
        t0 = time.time()
        try:
            upstream = urllib.request.urlopen(request, timeout=self.timeout_s)
        except urllib.error.HTTPError as exc:
            err_body = exc.read()
            self.send_response(exc.code)
            ctype = exc.headers.get("Content-Type", "application/json")
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(err_body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(err_body)
            self._vlog(f"UPSTREAM HTTP {exc.code} in {time.time()-t0:.2f}s")
            return
        except Exception as exc:  # noqa: BLE001
            msg = json.dumps({"error": {"message": f"lms proxy failure: {exc}"}}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(msg)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(msg)
            self._vlog(f"UPSTREAM FAIL {exc!r}")
            return

        try:
            content_type = upstream.headers.get("Content-Type", "application/json")
            status = upstream.status
            is_sse = "text/event-stream" in content_type

            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            # Avoid Transfer-Encoding: chunked — some SSE clients mis-handle it.
            if is_sse:
                self.end_headers()
                lines = 0
                saw_done = False
                saw_tool_calls = False
                while True:
                    raw_line = upstream.readline()
                    if not raw_line:
                        break
                    try:
                        line = raw_line.decode("utf-8")
                    except UnicodeDecodeError:
                        self.wfile.write(raw_line)
                        self.wfile.flush()
                        continue
                    stripped = line.rstrip("\r\n")
                    if "tool_calls" in stripped:
                        saw_tool_calls = True
                    if stripped.strip() == "data: [DONE]":
                        saw_done = True
                    transformed = _transform_sse_line(stripped) + "\n"
                    self.wfile.write(transformed.encode("utf-8"))
                    self.wfile.flush()
                    lines += 1
                self._vlog(
                    f"SSE done lines={lines} saw_done={saw_done} "
                    f"had_tool_calls_field={saw_tool_calls} in {time.time()-t0:.2f}s"
                )
            else:
                raw = upstream.read()
                if raw[:1] in (b"{", b"["):
                    before = b'"tool_calls":[]' in raw.replace(b" ", b"")
                    raw = _transform_json_bytes(raw)
                    after = b'"tool_calls"' in raw
                    self._vlog(
                        f"JSON done bytes={len(raw)} stripped_empty={before and not after} "
                        f"in {time.time()-t0:.2f}s"
                    )
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
        finally:
            upstream.close()

    def do_GET(self) -> None:  # noqa: N802
        self._forward()

    def do_POST(self) -> None:  # noqa: N802
        self._forward()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1240)
    parser.add_argument("--upstream", default="http://127.0.0.1:1234")
    parser.add_argument("--timeout-s", type=float, default=600.0)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    ProxyHandler.upstream_base = args.upstream.rstrip("/")
    ProxyHandler.timeout_s = args.timeout_s
    ProxyHandler.verbose = not args.quiet

    class ReusableServer(ThreadingHTTPServer):
        allow_reuse_address = True

    server = ReusableServer((args.listen, args.port), ProxyHandler)
    print(
        f"lms_openai_proxy listening on http://{args.listen}:{args.port}/v1 "
        f"→ {ProxyHandler.upstream_base}/v1 (stripping empty tool_calls)",
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\nstopping", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
